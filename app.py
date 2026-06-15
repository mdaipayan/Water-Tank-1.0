"""
app.py – Elevated RCC Water Tank Design Suite
Streamlit multi-tab application implementing IS 3370:2009 / IS 456:2000
"""
import math, io, sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from src.design.base import CONCRETE, STEEL, SEISMIC_ZONE, WIND_BASIC_SPEED
from src.design.circular_tank import design_circular_tank
from src.design.intze_tank import design_intze_tank
from src.design.rectangular_tank import design_rectangular_tank
from src.design.seismic import seismic_forces, wind_forces
from src.design.optimizer import rank_tank_types, auto_redesign_if_failed
from src.design.foundation import foundation_from_result
from src.report.pdf_report import generate_pdf_report, _pretty as _rl_pretty
from src.drawing.tank_drawings import dispatch_drawing, draw_bbs_chart


# ── UI helpers: prettified labels (sub/superscripts) + worked formulas ────────
def _ui_pretty(key):
    lab, unit = _rl_pretty(key)
    conv = lambda s: (s or "").replace("<super>", "<sup>").replace("</super>", "</sup>")
    return conv(lab), conv(unit)


def _ui_fmt(v):
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:,.1f}"
    return str(v)


def _param_table_html(details):
    rows = []
    for k, v in details.items():
        lab, unit = _ui_pretty(k)
        val = f"{_ui_fmt(v)} {unit}" if unit else _ui_fmt(v)
        rows.append(
            f"<tr><td style='padding:3px 12px;border-bottom:1px solid #eef2f7'>{lab}</td>"
            f"<td style='padding:3px 12px;border-bottom:1px solid #eef2f7;text-align:right;"
            f"font-weight:600;color:#004B7F'>{val}</td></tr>")
    return ("<table style='width:100%;border-collapse:collapse;font-size:0.86rem'>"
            "<tr><th style='text-align:left;padding:5px 12px;background:#E8F1F8;color:#004B7F'>Parameter</th>"
            "<th style='text-align:right;padding:5px 12px;background:#E8F1F8;color:#004B7F'>Value</th></tr>"
            + "".join(rows) + "</table>")


def _render_calc_formulas(formulas):
    for fdef in (formulas or []):
        if fdef.get("label"):
            ref = f" &nbsp;·&nbsp; *{fdef['ref']}*" if fdef.get("ref") else ""
            st.markdown(f"**{fdef['label']}**{ref}")
        st.latex(fdef["latex"])

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Elevated RCC Water Tank Design",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #004B7F 0%, #0070BE 100%);
    color: white; padding: 1.4rem 2rem; border-radius: 10px;
    margin-bottom: 1.2rem;
    box-shadow: 0 4px 15px rgba(0,75,127,0.25);
}
.main-header h1 { margin:0; font-size:1.6rem; font-weight:700; }
.main-header p  { margin:0.3rem 0 0; font-size:0.85rem; opacity:0.88; }

.metric-card {
    background: white; border-left: 4px solid #004B7F;
    border-radius: 8px; padding: 0.9rem 1.1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    margin-bottom: 0.6rem;
}
.metric-card .label { font-size: 0.72rem; color: #666; text-transform: uppercase;
                       letter-spacing: 0.05em; }
.metric-card .value { font-size: 1.4rem; font-weight: 700; color: #004B7F; }
.metric-card .unit  { font-size: 0.78rem; color: #888; margin-left: 3px; }

.ok-badge   { background:#E8F5E9; color:#2E7D32; border-radius:20px;
              padding:3px 10px; font-size:0.8rem; font-weight:600; }
.fail-badge { background:#FFEBEE; color:#C62828; border-radius:20px;
              padding:3px 10px; font-size:0.8rem; font-weight:600; }
.warn-badge { background:#FFF8E1; color:#F57F17; border-radius:20px;
              padding:3px 10px; font-size:0.8rem; font-weight:600; }

.comp-card {
    border: 1px solid #E0E7EF; border-radius: 8px;
    padding: 0.9rem 1rem; margin-bottom: 0.7rem;
    background: #FAFCFF;
}
.comp-title { font-weight:600; font-size:0.95rem; color:#004B7F; margin-bottom:0.4rem; }

.section-header {
    background: #E8F1F8; border-left: 4px solid #004B7F;
    padding: 0.5rem 0.9rem; border-radius: 0 6px 6px 0;
    font-weight: 600; font-size:1rem; color:#004B7F;
    margin: 1rem 0 0.6rem;
}

.is-ref {
    background:#FFF8E1; border:1px solid #CC9900; border-radius:6px;
    padding:0.5rem 0.8rem; font-size:0.8rem; color:#5D4037; margin:0.4rem 0;
}

.opt-best  { background:#E8F5E9; border:2px solid #2E7D32; border-radius:8px;
             padding:0.7rem 1rem; margin:0.4rem 0; }
.opt-other { background:#FAFAFA; border:1px solid #ddd; border-radius:8px;
             padding:0.7rem 1rem; margin:0.4rem 0; }

.bbs-total { background:#004B7F; color:white; font-weight:700;
             border-radius:6px; padding:0.4rem 0.8rem; text-align:right; }

stTabs [data-baseweb="tab"] { font-size:0.9rem; font-weight:500; }
stTabs [aria-selected="true"] { color:#004B7F !important; border-bottom:3px solid #004B7F !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🏗️ Elevated RCC Water Tank Design Suite</h1>
  <p>IS 3370:2009 | IS 456:2000 | IS 875:2015 | IS 1893 Part 2:2016 &nbsp;·&nbsp;
     Working Stress Method (WSM) &nbsp;·&nbsp;
     Circular · Rectangular · Intze tanks</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar – Inputs
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Design Parameters")
    st.markdown("---")

    st.markdown("#### 📋 Project Info")
    project_name = st.text_input("Project Name", value="EWT-001")
    location     = st.text_input("Location / Site", value="Nagpur, Maharashtra")

    st.markdown("#### 💧 Tank Requirements")
    capacity = st.number_input("Required Capacity (m³)", min_value=10.0,
                                max_value=5000.0, value=500.0, step=50.0)
    free_board = st.number_input("Free Board (m)", min_value=0.15,
                                  max_value=0.60, value=0.30, step=0.05)

    st.markdown("#### 🏗️ Staging")
    staging_h = st.number_input("Staging Height (m)", min_value=5.0,
                                 max_value=30.0, value=12.0, step=1.0)
    n_cols    = st.selectbox("No. of Staging Columns", [4, 6, 8, 12], index=1)

    st.markdown("#### 🧱 Materials")
    conc_grade  = st.selectbox("Concrete Grade", list(CONCRETE.keys()), index=1)
    steel_grade = st.selectbox("Steel Grade", list(STEEL.keys()), index=1)

    st.markdown("#### 🌍 Site Conditions")
    seismic_zone  = st.selectbox("Seismic Zone",
                                  list(SEISMIC_ZONE.keys()), index=1,
                                  format_func=lambda z: SEISMIC_ZONE[z]["label"])
    imp_factor    = st.selectbox("Importance Factor (I)",
                                  [1.0, 1.5], index=1,
                                  format_func=lambda x: f"{x} – {'Drinking / Fire' if x==1.5 else 'Other'}")
    soil_type     = st.selectbox("Soil Type", ["I","II","III"], index=1,
                                  format_func=lambda s: {"I":"I – Hard Rock","II":"II – Medium","III":"III – Soft"}[s])
    sbc           = st.number_input("Soil Safe Bearing Capacity (kN/m²)",
                                    min_value=50.0, max_value=600.0,
                                    value=150.0, step=25.0)
    wind_speed    = st.selectbox("Basic Wind Speed (m/s)",
                                  [33, 39, 44, 47, 50, 55], index=2)

    st.markdown("#### 🔧 Tank Type")
    tank_mode = st.radio("Selection Mode",
                          ["🤖 Auto-Optimise (Recommend Best)",
                           "⚙️ Manual Selection"],
                          index=0)
    if "Manual" in tank_mode:
        tank_choice = st.selectbox("Tank Type",
                                    ["Circular (Cylindrical) Flat-Bottom",
                                     "Intze Tank",
                                     "Rectangular Tank"])
    else:
        tank_choice = None

    if "Intze" in (tank_choice or ""):
        cone_angle = st.slider("Cone Angle (°)", 30, 60, 45, 5)
        h_d_intze  = st.slider("H/D Ratio (Cylinder)", 0.3, 0.8, 0.5, 0.05)
    else:
        cone_angle = 45
        h_d_intze  = 0.5

    st.markdown("---")
    run_btn = st.button("🚀 Run Design", type="primary", use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
if "result"       not in st.session_state: st.session_state.result       = None
if "ranked"       not in st.session_state: st.session_state.ranked       = None
if "seismic_res"  not in st.session_state: st.session_state.seismic_res  = None
if "wind_res"     not in st.session_state: st.session_state.wind_res     = None
if "found_res"    not in st.session_state: st.session_state.found_res    = None

# ─────────────────────────────────────────────────────────────────────────────
# RUN DESIGN
# ─────────────────────────────────────────────────────────────────────────────
if run_btn:
    with st.spinner("Running IS 3370 WSM design calculations…"):
        try:
            # ── 1. Optimise / select ────────────────────────────────────────
            ranked = rank_tank_types(
                capacity_m3=capacity,
                concrete_grade=conc_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_h,
                n_columns=n_cols,
            )
            st.session_state.ranked = ranked

            if "Manual" in tank_mode and tank_choice:
                # find matching result
                matched = next((r for nm, r, _ in ranked
                                if nm.lower() in tank_choice.lower()
                                or tank_choice.lower() in nm.lower()), None)
                if matched is None:
                    # design manually
                    if "Intze" in tank_choice:
                        matched = design_intze_tank(
                            capacity_m3=capacity, H_D_ratio=h_d_intze,
                            concrete_grade=conc_grade, steel_grade=steel_grade,
                            cone_angle_deg=cone_angle, staging_height_m=staging_h,
                            n_columns=n_cols, free_board_m=free_board)
                    elif "Rect" in tank_choice:
                        matched = design_rectangular_tank(
                            capacity_m3=capacity, concrete_grade=conc_grade,
                            steel_grade=steel_grade, free_board_m=free_board,
                            staging_height_m=staging_h, n_columns=n_cols)
                    else:
                        matched = design_circular_tank(
                            capacity_m3=capacity, concrete_grade=conc_grade,
                            steel_grade=steel_grade, free_board_m=free_board,
                            staging_height_m=staging_h, n_columns=n_cols)
                result = matched
            else:
                if ranked:
                    _, result, _ = ranked[0]   # best
                else:
                    st.error("No feasible tank type for given capacity range.")
                    st.stop()

            # ── 2. Auto-redesign if failed ─────────────────────────────────
            if not result.ok:
                with st.spinner("⚠️ Design inadequate — attempting auto-redesign…"):
                    result = auto_redesign_if_failed(
                        result, capacity, conc_grade, steel_grade, staging_h)

            st.session_state.result = result

            # ── 3. Seismic & Wind ──────────────────────────────────────────
            W_empty = result.volumes.get("total_concrete_m3", 100) * 25.0
            try:
                st.session_state.seismic_res = seismic_forces(
                    tank_type=result.tank_type,
                    capacity_m3=capacity,
                    geometry=result.geometry,
                    W_empty_tank_kN=W_empty,
                    staging_height_m=staging_h,
                    zone=seismic_zone,
                    importance_factor=imp_factor,
                    soil_type=soil_type,
                )
            except Exception as e:
                st.session_state.seismic_res = {"error": str(e)}

            try:
                st.session_state.wind_res = wind_forces(
                    geometry=result.geometry,
                    basic_wind_speed_m_s=float(wind_speed),
                    staging_height_m=staging_h,
                )
            except Exception as e:
                st.session_state.wind_res = {"error": str(e)}

            # ── 4. Foundation & stability ──────────────────────────────────
            try:
                st.session_state.found_res = foundation_from_result(
                    result,
                    seismic_result=st.session_state.seismic_res
                    if isinstance(st.session_state.seismic_res, dict)
                    and "error" not in st.session_state.seismic_res else None,
                    wind_result=st.session_state.wind_res
                    if isinstance(st.session_state.wind_res, dict)
                    and "error" not in st.session_state.wind_res else None,
                    sbc_kN_m2=float(sbc),
                    concrete=CONCRETE[conc_grade],
                    steel=STEEL[steel_grade],
                )
            except Exception as e:
                st.session_state.found_res = None

            st.success(f"✅ Design complete — **{result.tank_type}** "
                       f"({'Adequate' if result.ok else 'Needs Review'})")
        except Exception as ex:
            st.error(f"Design engine error: {ex}")
            import traceback; st.code(traceback.format_exc())

# ─────────────────────────────────────────────────────────────────────────────
# Display Results
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.result is None:
    st.info("👈 Set parameters in the sidebar and click **Run Design** to begin.")
    with st.expander("ℹ️ About this application", expanded=True):
        st.markdown("""
        ### Elevated RCC Water Tank Design Suite
        This application performs **Working Stress Method (WSM)** design of elevated
        reinforced concrete water tanks per Indian Standard codes:

        | Code | Scope |
        |------|-------|
        | **IS 3370:2009** (Parts I–IV) | Concrete structures for liquid storage |
        | **IS 456:2000** | Plain & reinforced concrete |
        | **IS 875** (Parts 1–3) | Dead, live & wind loads |
        | **IS 1893 Part 2:2016** | Seismic design of tanks |

        **Tank types supported:**
        - 🔵 **Circular (Cylindrical) Flat-Bottom** – 10–5000 m³
        - 📦 **Rectangular** – 5–300 m³  
        - 🏆 **Intze Tank** – 100–10,000 m³ (most efficient for large capacities)

        **Features:** Auto-optimisation · Auto-redesign on failure · PDF report ·
        Bar Bending Schedule · Cost Estimate · Schematic drawings
        """)
    st.stop()

res  = st.session_state.result
rank = st.session_state.ranked
seis = st.session_state.seismic_res
wind = st.session_state.wind_res
found = st.session_state.found_res

# ── Top KPI row ──────────────────────────────────────────────────────────────
ok_html = ('<span class="ok-badge">✅ ADEQUATE</span>'
           if res.ok else '<span class="fail-badge">❌ NEEDS REVISION</span>')
c1, c2, c3, c4, c5 = st.columns(5)
for col, label, val, unit in [
    (c1, "Tank Type",    res.tank_type.split("(")[0].strip(), ""),
    (c2, "Capacity",     f"{res.capacity_m3:,.0f}", "m³"),
    (c3, "Total Cost",   f"₹{res.cost_estimate.get('total',0):,.0f}", ""),
    (c4, "Concrete",     f"{res.volumes.get('total_concrete_m3',0):.1f}", "m³"),
    (c5, "Steel",        f"{res.volumes.get('total_steel_kg',0):,.0f}", "kg"),
]:
    col.markdown(f"""
    <div class="metric-card">
      <div class="label">{label}</div>
      <div class="value">{val}<span class="unit">{unit}</span></div>
    </div>""", unsafe_allow_html=True)

st.markdown(f"**Design Status:** {ok_html}", unsafe_allow_html=True)
if res.warnings:
    with st.expander(f"⚠️ {len(res.warnings)} Warning(s)", expanded=not res.ok):
        for w in res.warnings:
            st.warning(w)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Optimisation",
    "📐 Geometry",
    "⚙️ Design Calcs",
    "🌍 Seismic & Wind",
    "📏 Bar Bending Schedule",
    "💰 Cost Estimate",
    "🎨 Drawings & PDF",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OPTIMISATION
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-header">Tank Type Optimisation & Selection</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="is-ref">
    📖 All feasible tank types are designed and ranked by <b>cost per m³ capacity</b>
    (lower = more economical). The ✅ recommended type is highlighted.
    </div>""", unsafe_allow_html=True)

    if rank:
        for i, (nm, r, sc) in enumerate(rank):
            is_best = (i == 0)
            card_cls = "opt-best" if is_best else "opt-other"
            badge    = "✅ RECOMMENDED" if is_best else f"#{i+1}"
            st.markdown(f"""
            <div class="{card_cls}">
              <b>{badge} — {nm}</b>
              &nbsp;&nbsp;<span style="font-size:0.82rem;color:#555">
              Cost/m³: ₹{sc['cost_per_m3']:,.0f} &nbsp;|&nbsp;
              Concrete: {r.volumes.get('total_concrete_m3',0):.1f} m³ &nbsp;|&nbsp;
              Steel: {r.volumes.get('total_steel_kg',0):.0f} kg &nbsp;|&nbsp;
              Design OK: {'✅' if r.ok else '❌'}
              </span><br>
              <span style="font-size:0.82rem">{sc['recommendation']}</span>
            </div>""", unsafe_allow_html=True)

        # Comparison table
        st.markdown("#### Comparative Summary")
        df_rank = pd.DataFrame([{
            "Rank": f"#{i+1}", "Tank Type": nm,
            "Volume Prov. (m³)": r.volumes.get("total_concrete_m3",0),
            "Total Cost (₹)": f"₹{r.cost_estimate.get('total',0):,.0f}",
            "Cost/m³ Capacity (₹)": f"₹{sc['cost_per_m3']:,.0f}",
            "Concrete (m³)": r.volumes.get("total_concrete_m3",0),
            "Steel (kg)": r.volumes.get("total_steel_kg",0),
            "Design OK": "✅" if r.ok else "❌",
            "Score": sc["composite_score"],
        } for i, (nm, r, sc) in enumerate(rank)])
        st.dataframe(df_rank.set_index("Rank"), use_container_width=True)

        # Cost bar chart
        if len(rank) > 1:
            fig_cmp, ax_cmp = plt.subplots(figsize=(7, 3.5), facecolor="#FAFAFA")
            names = [nm for nm, _, _ in rank]
            costs = [sc["cost_per_m3"] for _, _, sc in rank]
            cols  = ["#004B7F" if i == 0 else "#AEC6CF" for i in range(len(rank))]
            bars  = ax_cmp.bar(names, costs, color=cols, edgecolor="white", width=0.5)
            for bar, cost in zip(bars, costs):
                ax_cmp.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + max(costs) * 0.01,
                            f"₹{cost:,.0f}", ha="center", fontsize=8, color="#333")
            ax_cmp.set_ylabel("Cost per m³ Capacity (₹)", fontsize=8)
            ax_cmp.set_title("Cost Efficiency Comparison", fontsize=9,
                              color="#004B7F", fontweight="bold")
            ax_cmp.set_facecolor("#FAFAFA")
            ax_cmp.spines[["top","right"]].set_visible(False)
            ax_cmp.tick_params(labelsize=8)
            st.pyplot(fig_cmp, use_container_width=True)
            plt.close(fig_cmp)
    else:
        st.info("Run design to see optimisation results.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — GEOMETRY
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-header">Tank Geometry & Dimensions</div>',
                unsafe_allow_html=True)
    geo = res.geometry
    cols = st.columns(2)
    geo_items = list(geo.items())
    mid = len(geo_items) // 2
    for col, items in zip(cols, [geo_items[:mid], geo_items[mid:]]):
        for k, v in items:
            col.metric(k.replace("_", " ").title(), v)

    # Material summary
    st.markdown("#### Materials Specified")
    c1, c2 = st.columns(2)
    cdata = CONCRETE[conc_grade]
    sdata = STEEL[steel_grade]
    with c1:
        st.markdown(f"""
        **Concrete: {conc_grade}**
        - f_ck = {cdata['fck']} N/mm²
        - σ_cbc = {cdata['sigma_cbc']} N/mm²
        - m (modular ratio) = {cdata['m']:.2f}
        """)
        st.markdown('<div class="is-ref">📖 IS 3370 Part II, Table 1 – Permissible stresses in concrete</div>',
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        **Steel: {steel_grade}**
        - f_y = {sdata['fy']} N/mm²
        - σ_st (bending) = {sdata['sigma_st_b']} N/mm²
        - σ_st (direct)  = {sdata['sigma_st_d']} N/mm²
        """)
        st.markdown('<div class="is-ref">📖 IS 3370 Part II, Table 2 – Permissible stresses in steel</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DESIGN CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-header">Component-Wise Design Calculations (WSM)</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="is-ref">
    📖 All calculations use <b>Working Stress Method (WSM)</b> mandated by
    IS 3370:2009 for liquid-retaining structures.
    Cover to water face = 45 mm | Min. concrete grade = M25
    </div>""", unsafe_allow_html=True)

    for comp in res.components:
        icon = "✅" if comp.ok else "❌"
        with st.expander(f"{icon} {comp.name}", expanded=comp.ok and bool(comp.details)):
            if comp.warnings:
                for w in comp.warnings:
                    st.warning(w)

            if comp.details:
                st.markdown(_param_table_html(comp.details), unsafe_allow_html=True)

            if getattr(comp, "formulas", None):
                st.markdown("##### 📐 Worked design calculations")
                _render_calc_formulas(comp.formulas)

    # Reinforcement summary
    st.markdown("#### 🔩 Reinforcement Provision Summary")
    st.markdown('<div class="is-ref">📖 IS 3370 Part II cl. 7 – Minimum reinforcement: 0.24% for Fe415/500</div>',
                unsafe_allow_html=True)

    rw_rows = []
    for comp_name, details in res.reinforcement.items():
        if not isinstance(details, dict):
            continue
        dia   = (details.get("bar_dia") or details.get("hoop_bar_dia") or
                 details.get("vert_bar_dia") or details.get("long_bar_dia") or "—")
        sp    = (details.get("bar_spacing_mm") or details.get("hoop_spacing_mm") or
                 details.get("vert_spacing_mm") or details.get("spacing") or "—")
        ast_r = (details.get("Ast_hoop_mm2_per_m") or details.get("Ast_mm2_per_m") or
                 details.get("Ast_mer_mm2_per_m") or details.get("Ast_mrb_mm2") or "—")
        ast_p = details.get("Ast_prov") or details.get("Ast_hoop_prov") or "—"
        rw_rows.append({
            "Component": comp_name.replace("_", " ").title(),
            "Bar Dia (mm)": dia,
            "Spacing (mm)": sp,
            "Ast Required (mm²/m)": ast_r,
            "Ast Provided (mm²/m)": ast_p,
        })
    if rw_rows:
        st.dataframe(pd.DataFrame(rw_rows), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — SEISMIC & WIND
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header">Seismic & Wind Analysis</div>',
                unsafe_allow_html=True)

    col_s, col_w = st.columns(2)

    with col_s:
        st.markdown("#### 🌍 Seismic – IS 1893 Part 2:2016 (Two-Mass Model)")
        st.markdown("""
        <div class="is-ref">
        📖 The tank is modelled as a two-DOF system with <b>impulsive (mᵢ)</b>
        and <b>convective (mᶜ)</b> liquid masses.
        Base shear V_B = √(V_i² + V_c²)
        </div>""", unsafe_allow_html=True)
        if seis and "error" not in seis:
            # KPIs
            s1, s2, s3 = st.columns(3)
            s1.metric("Base Shear V_B", f"{seis['V_B_kN']:.1f} kN")
            s2.metric("OTM at base", f"{seis['M_ot_kNm']:.1f} kN·m")
            s3.metric("Zone Factor Z", seis["Z"])
            df_seis = pd.DataFrame(
                [(_ui_pretty(k)[0], f"{_ui_fmt(v)} {_ui_pretty(k)[1] or ''}")
                 for k, v in seis.items() if k != "formulas"],
                columns=["Parameter", "Value"])
            st.markdown(_param_table_html({k: v for k, v in seis.items() if k != "formulas"}),
                        unsafe_allow_html=True)

            # Spectral chart
            T_arr = np.linspace(0.01, 4.0, 200)
            def Sa_g(T, st_type="II"):
                if st_type == "I":
                    if T <= 0.10: return 1 + 15 * T
                    elif T <= 0.40: return 2.50
                    elif T <= 4.00: return 1.00 / T
                    return 0.25
                elif st_type == "II":
                    if T <= 0.10: return 1 + 15 * T
                    elif T <= 0.55: return 2.50
                    elif T <= 4.00: return 1.36 / T
                    return 0.34
                else:
                    if T <= 0.10: return 1 + 15 * T
                    elif T <= 0.67: return 2.50
                    elif T <= 4.00: return 1.67 / T
                    return 0.42
            Sa_arr = [Sa_g(t, soil_type) for t in T_arr]
            fig_sp, ax_sp = plt.subplots(figsize=(5, 2.8), facecolor="#FAFAFA")
            ax_sp.plot(T_arr, Sa_arr, color="#004B7F", lw=1.5)
            ax_sp.axvline(seis.get("T_i_sec", 0), color="#C0392B", lw=1.2,
                          ls="--", label=f"Ti={seis.get('T_i_sec',0):.3f}s")
            ax_sp.axvline(seis.get("T_c_sec", 0), color="#CC9900", lw=1.2,
                          ls="--", label=f"Tc={seis.get('T_c_sec',0):.3f}s")
            ax_sp.set_xlabel("Period T (s)", fontsize=7); ax_sp.set_ylabel("Sa/g", fontsize=7)
            ax_sp.set_title(f"Response Spectrum – Soil Type {soil_type}", fontsize=8,
                            color="#004B7F")
            ax_sp.legend(fontsize=7); ax_sp.grid(alpha=0.3, lw=0.4)
            ax_sp.set_facecolor("#FAFAFA")
            st.pyplot(fig_sp, use_container_width=True)
            plt.close(fig_sp)

            if seis.get("formulas"):
                st.markdown("##### 📐 Worked calculations")
                _render_calc_formulas(seis["formulas"])
        elif seis and "error" in seis:
            st.error(f"Seismic calculation error: {seis['error']}")

    with col_w:
        st.markdown("#### 💨 Wind – IS 875 Part 3:2015")
        st.markdown("""
        <div class="is-ref">
        📖 Design wind pressure p_z = 0.6 V_z² (IS 875 Part 3, cl. 7.2)
        where V_z = V_b · k₁ · k₂ · k₃
        </div>""", unsafe_allow_html=True)
        if wind and "error" not in wind:
            w1, w2 = st.columns(2)
            w1.metric("Wind Base Shear", f"{wind['V_wind_kN']:.1f} kN")
            w2.metric("Wind OTM", f"{wind['M_wind_kNm']:.1f} kN·m")
            st.markdown(_param_table_html({k: v for k, v in wind.items() if k != "formulas"}),
                        unsafe_allow_html=True)

            # Governing load
            if seis and "V_B_kN" in seis:
                V_seis = seis["V_B_kN"]
                V_wind = wind["V_wind_kN"]
                govern = "Seismic" if V_seis > V_wind else "Wind"
                st.info(f"🏆 **Governing lateral load: {govern}** "
                        f"(Seismic V_B={V_seis:.1f} kN vs Wind V={V_wind:.1f} kN)")

            if wind.get("formulas"):
                st.markdown("##### 📐 Worked calculations")
                _render_calc_formulas(wind["formulas"])
        elif wind and "error" in wind:
            st.error(f"Wind calculation error: {wind['error']}")

    # ── Foundation & Stability ───────────────────────────────────────────────
    st.markdown('<div class="section-header">Foundation & Global Stability</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="is-ref">
    📖 Isolated square footing under each staging column (WSM). Bearing checked
    against SBC (+25% for wind/seismic combos); footing depth from punching shear
    (IS 456 cl. B-5); global overturning &amp; sliding factors of safety.
    </div>""", unsafe_allow_html=True)
    if found is not None:
        fd = found.details
        ok_badge = ('<span class="ok-badge">✅ STABLE</span>' if found.ok
                    else '<span class="fail-badge">❌ CHECK REQUIRED</span>')
        st.markdown(f"**Foundation status:** {ok_badge}", unsafe_allow_html=True)
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Footing Size", f"{fd['footing_size_m']:.2f} m sq")
        f2.metric("Thickness", f"{fd['footing_thickness_mm']} mm")
        f3.metric("Bearing Press.", f"{fd['bearing_pressure_kN_m2']:.0f} kN/m²",
                  help=f"Allowable {fd['sbc_allow_kN_m2']:.0f} kN/m²")
        f4.metric("Max Col. Load", f"{fd['P_max_kN']:.0f} kN")
        g1, g2, g3 = st.columns(3)
        g1.metric("FoS Overturning", fd["FoS_overturning"] if fd["FoS_overturning"] else "—")
        g2.metric("FoS Sliding", fd["FoS_sliding"] if fd["FoS_sliding"] else "—")
        g3.metric("Uplift?", "Yes ⚠️" if fd["uplift"] else "No")
        if found.warnings:
            for w in found.warnings:
                st.warning(w)
        with st.expander("Footing reinforcement & full details"):
            st.markdown(_param_table_html(fd), unsafe_allow_html=True)
        if getattr(found, "formulas", None):
            st.markdown("##### 📐 Worked calculations")
            _render_calc_formulas(found.formulas)
    else:
        st.info("Foundation results unavailable for this run.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — BAR BENDING SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-header">Bar Bending Schedule (BBS)</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="is-ref">
    📖 Unit weight = d²/162.2 kg/m · Hooks & laps per IS 2502 · Cover per IS 3370 Part I
    </div>""", unsafe_allow_html=True)

    bbs = res.bbs
    if bbs:
        df_bbs = pd.DataFrame(bbs)
        total_wt  = df_bbs["weight_kg"].sum()
        total_len = df_bbs["total_length_m"].sum()

        # Summary metrics
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Total Bar Marks",    len(df_bbs))
        b2.metric("Total Length (m)",   f"{total_len:,.1f}")
        b3.metric("Total Weight (kg)",  f"{total_wt:,.1f}")
        b4.metric("Avg. Weight/Mark",   f"{total_wt/len(df_bbs):.1f} kg")

        # Styled dataframe (falls back to a plain table if jinja2 is unavailable)
        try:
            st.dataframe(
                df_bbs.style
                  .format({"cut_length_m": "{:.3f}", "total_length_m": "{:.2f}",
                           "weight_kg": "{:.2f}"})
                  .background_gradient(subset=["weight_kg"], cmap="Blues"),
                use_container_width=True, hide_index=True
            )
        except (ImportError, AttributeError):
            st.dataframe(
                df_bbs.round({"cut_length_m": 3, "total_length_m": 2, "weight_kg": 2}),
                use_container_width=True, hide_index=True
            )

        st.markdown(f"""
        <div class="bbs-total">
        Total Steel Weight: {total_wt:,.1f} kg &nbsp;|&nbsp;
        Total Bar Length: {total_len:,.1f} m &nbsp;|&nbsp;
        No. of Bar Marks: {len(df_bbs)}
        </div>""", unsafe_allow_html=True)

        # BBS charts
        try:
            bbs_chart = draw_bbs_chart(bbs)
            st.image(bbs_chart, use_container_width=True)
        except Exception as e:
            st.warning(f"Chart error: {e}")

        # Download BBS as CSV
        csv_bbs = df_bbs.to_csv(index=False).encode()
        st.download_button("📥 Download BBS as CSV", csv_bbs,
                           file_name=f"BBS_{project_name}.csv",
                           mime="text/csv")
    else:
        st.info("No BBS data generated for this tank type yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — COST ESTIMATE
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<div class="section-header">Abstract of Cost Estimate</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div class="is-ref">
    📖 Rates based on DSR 2023-24 (indicative). For tendering, use site-specific BOQ.
    GST @ 18% applicable on all items.
    </div>""", unsafe_allow_html=True)

    vol = res.volumes
    ce  = res.cost_estimate

    # Cost breakdown pie
    cost_items = {
        "Concrete Works": ce.get("concrete_cost", 0),
        "Steel (Supply & Fix)": ce.get("steel_cost", 0),
        "Waterproofing": ce.get("total", 0) * 0.04,
        "Foundation": ce.get("total", 0) * 0.10,
        "Misc / Ladder / Platform": ce.get("total", 0) * 0.02,
    }
    subtotal = sum(cost_items.values())
    gst_val  = subtotal * 0.18
    grand    = subtotal + gst_val

    c_e1, c_e2 = st.columns([1, 1])
    with c_e1:
        fig_pie, ax_pie = plt.subplots(figsize=(5, 4), facecolor="#FAFAFA")
        explode = [0.04] * len(cost_items)
        wedges, texts, auto = ax_pie.pie(
            list(cost_items.values()),
            labels=list(cost_items.keys()),
            autopct="%1.1f%%",
            explode=explode,
            colors=["#004B7F","#CC9900","#27AE60","#8E44AD","#E67E22"],
            startangle=140,
            textprops={"fontsize": 7.5},
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        )
        ax_pie.set_title("Cost Breakdown", fontsize=9,
                         color="#004B7F", fontweight="bold")
        ax_pie.set_facecolor("#FAFAFA")
        st.pyplot(fig_pie, use_container_width=True)
        plt.close(fig_pie)

    with c_e2:
        # Volumes table
        st.markdown("**Concrete Volume Summary**")
        vol_df = pd.DataFrame(
            [(k.replace("_", " ").title(), f"{v:.2f} m³" if "m3" in k else str(v))
             for k, v in vol.items()],
            columns=["Item", "Quantity"]
        )
        st.dataframe(vol_df, use_container_width=True, hide_index=True)

        st.markdown("**Cost Summary**")
        cost_df = pd.DataFrame([
            {"Item": "Concrete Works (incl. formwork)",
             "Amount": f"₹{ce.get('concrete_cost',0):,.0f}"},
            {"Item": "Steel Reinforcement (supply & fix)",
             "Amount": f"₹{ce.get('steel_cost',0):,.0f}"},
            {"Item": "Waterproofing (2-coat epoxy)",
             "Amount": f"₹{ce.get('total',0)*0.04:,.0f}"},
            {"Item": "Foundation (assumed)",
             "Amount": f"₹{ce.get('total',0)*0.10:,.0f}"},
            {"Item": "Misc / Platform / Ladder",
             "Amount": f"₹{ce.get('total',0)*0.02:,.0f}"},
            {"Item": "Sub Total",        "Amount": f"₹{subtotal:,.0f}"},
            {"Item": "GST @ 18%",        "Amount": f"₹{gst_val:,.0f}"},
            {"Item": "🏷️ GRAND TOTAL",  "Amount": f"₹{grand:,.0f}"},
        ])
        st.dataframe(cost_df, use_container_width=True, hide_index=True)

    # Per-m³ cost
    st.metric("Cost per m³ Tank Capacity",
              f"₹{grand / capacity:,.0f} / m³",
              help="Lower values indicate more economical design")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — DRAWINGS & PDF
# ══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown('<div class="section-header">Schematic Drawings & PDF Report</div>',
                unsafe_allow_html=True)

    d_col1, d_col2 = st.columns([3, 1])

    with d_col1:
        st.markdown("#### 📐 Structural Schematic Drawing")
        try:
            with st.spinner("Generating drawing…"):
                drawing_bytes = dispatch_drawing(
                    res.tank_type, res.geometry, res.reinforcement)
            st.image(drawing_bytes, use_container_width=True,
                     caption=f"{res.tank_type} – IS 3370:2009 Design")
            st.download_button(
                "📥 Download Drawing (PNG)",
                drawing_bytes,
                file_name=f"Drawing_{project_name}_{res.tank_type[:10]}.png",
                mime="image/png",
            )
        except Exception as e:
            st.error(f"Drawing error: {e}")

    with d_col2:
        st.markdown("#### 📄 PDF Report")
        st.markdown("""
        Professional design report including:
        - ✅ Cover sheet & project info
        - 📊 Tank type optimisation table
        - 📐 Geometry & dimensions
        - ⚙️ Component design calculations
        - 🌍 Seismic & wind analysis
        - 🔩 Reinforcement summary
        - 📏 Bar Bending Schedule
        - 💰 Cost estimate
        - 📖 IS code references
        """)

        if st.button("🔨 Generate PDF Report", type="primary",
                     use_container_width=True):
            with st.spinner("Building PDF…"):
                try:
                    pdf_bytes = generate_pdf_report(
                        result=res,
                        project_name=project_name,
                        location=location,
                        seismic_result=seis,
                        wind_result=wind,
                        ranked_types=rank,
                        bbs_rows=res.bbs,
                        foundation_result=found,
                    )
                    st.download_button(
                        "📥 Download PDF Report",
                        pdf_bytes,
                        file_name=f"Design_Report_{project_name}.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True,
                    )
                    st.success("PDF ready!")
                except Exception as e:
                    st.error(f"PDF error: {e}")
                    import traceback; st.code(traceback.format_exc())

# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; font-size:0.78rem; color:#888; margin-top:0.5rem">
  Elevated RCC Water Tank Design Suite &nbsp;·&nbsp;
  IS 3370:2009 / IS 456:2000 / IS 875 / IS 1893 Part 2 &nbsp;·&nbsp;
  Dept. of Civil Engineering, KITS Ramtek &nbsp;·&nbsp;
  <i>For engineering use only – independent verification recommended</i>
</div>
""", unsafe_allow_html=True)
