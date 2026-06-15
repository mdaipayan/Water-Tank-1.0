"""
foundation.py - Isolated footing design and global stability for elevated tanks.

Designs one isolated square RCC footing under each staging column (Working Stress
Method, consistent with the rest of the suite) and checks global stability of the
tank against overturning and sliding under the governing lateral load.

References
----------
IS 456:2000   - cl. 34 (footings), cl. 26.2.1 (development length),
                cl. B-5 (WSM shear / punching: allowable punching = 0.16*sqrt(fck))
IS 1893 / IS 875 - lateral base shear & overturning moment (from seismic.py)
IS 3370:2009  - liquid-retaining detailing, minimum reinforcement

Notes / assumptions
-------------------
* Footings are square, sized on the SERVICE column load (WSM); a 25% overstress
  on SBC is permitted for load cases that include seismic or wind (IS 456 cl. 34
  / IS 1904 practice).
* Additional column axial from overturning for a ring of n equally spaced columns
  at radius R_col:  dP = 2*M_ot / (n * R_col)  (extreme column).
* Footing self weight + backfill allowed for as 10% of column load.
"""
from __future__ import annotations
import math
from .base import (ast_from_moment, choose_bar, neutral_axis, lever_arm,
                   ComponentResult)

MU_FRICTION = 0.50      # soil-concrete friction coefficient (cl. typical)
FOS_OVERTURN_MIN = 1.40  # with seismic/wind included
FOS_SLIDING_MIN = 1.40
SBC_OVERSTRESS_LATERAL = 1.25   # permissible SBC increase with wind/seismic


def development_length(dia_mm: float, fck: int, sigma_st: float,
                       deformed: bool = True) -> float:
    """
    Development length Ld (mm) per IS 456:2000 cl. 26.2.1 (WSM permissible bond).
    Ld = phi * sigma_st / (4 * tau_bd).  tau_bd from Table (M20->1.2, +0.2/grade),
    increased 60% for deformed (HYSD) bars.
    """
    tau_bd_base = {20: 1.2, 25: 1.4, 30: 1.5, 35: 1.7, 40: 1.9}.get(fck, 1.4)
    if deformed:
        tau_bd_base *= 1.6
    return dia_mm * sigma_st / (4.0 * tau_bd_base)


def design_foundation(
    P_col_service_kN: float,
    n_columns: int,
    R_col_m: float,
    col_size_m: float,
    M_ot_kNm: float = 0.0,
    V_lat_kN: float = 0.0,
    W_total_kN: float = 0.0,
    sbc_kN_m2: float = 150.0,
    concrete_grade_fck: int = 25,
    sigma_cbc: float = 8.5,
    sigma_st: float = 190.0,
    m_modular: float = 10.98,
    steel_min_pct: float = 0.12,
    cover_mm: float = 50.0,
) -> ComponentResult:
    """
    Design an isolated square footing under one staging column and check global
    stability of the tank. Returns a ComponentResult with details + warnings.
    """
    comp = ComponentResult("Isolated Column Footing & Stability")

    # ── Column axial including overturning effect ─────────────────────────────
    dP = (2.0 * M_ot_kNm / (n_columns * R_col_m)) if (n_columns and R_col_m) else 0.0
    P_max = P_col_service_kN + dP
    P_min = P_col_service_kN - dP

    # ── Footing plan size (service load + 10% for footing/backfill) ───────────
    sbc_eff = sbc_kN_m2 * (SBC_OVERSTRESS_LATERAL if M_ot_kNm > 0 else 1.0)
    A_req = (P_max * 1.10) / sbc_eff               # m²
    B_f = max(math.ceil(math.sqrt(A_req) * 4) / 4, 1.0)   # square side, 250 mm steps
    A_prov = B_f * B_f
    q_gross_max = (P_max * 1.10) / A_prov           # kN/m² bearing pressure

    bearing_ok = q_gross_max <= sbc_eff * 1.001
    if not bearing_ok:
        # enlarge until satisfied (safety net)
        while q_gross_max > sbc_eff and B_f < 12:
            B_f += 0.25
            A_prov = B_f * B_f
            q_gross_max = (P_max * 1.10) / A_prov
        bearing_ok = q_gross_max <= sbc_eff * 1.001

    # ── Net upward pressure for member design (column load / area) ────────────
    q_net = P_max / A_prov                           # kN/m²

    # ── Footing depth from punching (two-way) shear, WSM allowable ────────────
    # allowable punching stress tau_p_perm = 0.16*sqrt(fck) (IS 456 B-5.5, WSM)
    tau_p_perm = 0.16 * math.sqrt(concrete_grade_fck)        # N/mm²
    # solve d so that punching shear stress <= allowable:
    #   Vp = q_net*(A_prov - (a+d)^2);  tau = Vp/(perimeter*d);  perimeter=4(a+d)
    a = col_size_m
    d = 0.30                                          # start 300 mm effective depth
    for _ in range(60):
        crit = a + d
        Vp = q_net * (A_prov - crit * crit)           # kN
        perim = 4.0 * crit                             # m
        tau = (Vp * 1e3) / (perim * 1e3 * d * 1e3)     # N/mm²  (kN->N, m->mm)
        if tau <= tau_p_perm or d > 2.0:
            break
        d += 0.025
    d_punch = d

    # ── Footing depth / steel from bending at column face ─────────────────────
    proj = (B_f - a) / 2.0                            # cantilever projection (m)
    M_ftg = q_net * proj * proj / 2.0                 # kN·m per m width
    k = neutral_axis(m_modular, sigma_cbc, sigma_st)
    j = lever_arm(k)
    Q = 0.5 * sigma_cbc * k * j
    d_bend = math.sqrt(M_ftg * 1e6 / (Q * 1000)) if M_ftg > 0 else 0.0   # mm
    d_req_mm = max(d_punch * 1000, d_bend, 150)
    D_ftg_mm = math.ceil((d_req_mm + cover_mm + 8) / 25) * 25            # total, 25 mm steps
    d_prov_mm = D_ftg_mm - cover_mm - 8

    # ── One-way (beam) shear check at distance d from face (verification) ──────
    x = max(proj - d_prov_mm / 1000.0, 0.0)
    V_oneway = q_net * x                               # kN per m width
    tau_v = (V_oneway * 1e3) / (1000 * d_prov_mm)       # N/mm²
    tau_c_perm = 0.16 * math.sqrt(concrete_grade_fck)   # conservative WSM allowable
    oneway_ok = tau_v <= tau_c_perm * 1.05

    # ── Reinforcement (both directions, symmetric square footing) ─────────────
    Ast = ast_from_moment(M_ftg, d_prov_mm, sigma_st, m_modular, sigma_cbc)
    Ast_min = steel_min_pct / 100.0 * D_ftg_mm * 1000.0   # per m width, gross
    Ast = max(Ast, Ast_min)
    bar = choose_bar(Ast, 150)
    Ld = development_length(bar["dia"], concrete_grade_fck, sigma_st)

    # ── Global stability ──────────────────────────────────────────────────────
    fos_ot = (W_total_kN * R_col_m / M_ot_kNm) if M_ot_kNm > 0 else float("inf")
    fos_sl = (MU_FRICTION * W_total_kN / V_lat_kN) if V_lat_kN > 0 else float("inf")
    uplift = P_min < 0.0

    if fos_ot < FOS_OVERTURN_MIN:
        comp.fail(f"Overturning FoS={fos_ot:.2f} < {FOS_OVERTURN_MIN} - widen column "
                  f"ring or increase dead load / footing size.")
    if fos_sl < FOS_SLIDING_MIN:
        comp.fail(f"Sliding FoS={fos_sl:.2f} < {FOS_SLIDING_MIN} - provide shear key "
                  f"or enlarge footings.")
    if uplift:
        comp.warn(f"Net uplift on windward column (P_min={P_min:.1f} kN < 0) - "
                  f"provide tension anchorage / tie footings.")
    if not bearing_ok:
        comp.fail(f"Bearing pressure {q_gross_max:.1f} > SBC {sbc_eff:.0f} kN/m² "
                  f"even at {B_f:.2f} m footing.")
    if not oneway_ok:
        comp.warn(f"One-way shear stress {tau_v:.2f} > allowable {tau_c_perm:.2f} "
                  f"N/mm² - increase footing depth.")

    # Footings overlapping the adjacent column => isolated footings impractical.
    col_spacing = (2.0 * math.pi * R_col_m / n_columns) if n_columns else 1e9
    if B_f > col_spacing:
        comp.warn(f"Footing size {B_f:.2f} m exceeds column spacing "
                  f"{col_spacing:.2f} m - footings overlap; adopt an annular/circular "
                  f"raft instead of isolated footings.")

    comp.details = {
        "P_col_service_kN": round(P_col_service_kN, 1),
        "dP_overturning_kN": round(dP, 1),
        "P_max_kN": round(P_max, 1),
        "P_min_kN": round(P_min, 1),
        "footing_size_m": round(B_f, 2),
        "footing_thickness_mm": int(D_ftg_mm),
        "eff_depth_mm": int(d_prov_mm),
        "bearing_pressure_kN_m2": round(q_gross_max, 1),
        "sbc_allow_kN_m2": round(sbc_eff, 1),
        "M_face_kNm_per_m": round(M_ftg, 2),
        "Ast_mm2_per_m": round(Ast, 1),
        "bar_dia_mm": bar["dia"],
        "bar_spacing_mm": bar["spacing"],
        "Ast_prov_mm2_per_m": bar["Ast_prov"],
        "dev_length_mm": int(round(Ld)),
        "punching_tau_perm_N_mm2": round(tau_p_perm, 2),
        "oneway_tau_N_mm2": round(tau_v, 3),
        "FoS_overturning": round(fos_ot, 2) if math.isfinite(fos_ot) else None,
        "FoS_sliding": round(fos_sl, 2) if math.isfinite(fos_sl) else None,
        "uplift": uplift,
    }
    return comp


def _column_ring_radius(tank_type: str, geometry: dict) -> float:
    """Estimate the radius of the staging column ring from tank geometry."""
    tt = tank_type.lower()
    if "rect" in tt:
        L = geometry.get("L_m", 5.0); B = geometry.get("B_m", 4.0)
        return 0.8 * math.hypot(L / 2, B / 2)
    R = geometry.get("R_int_m", geometry.get("D_int_m", 6.0) / 2)
    return max(R, 1.0)


def foundation_from_result(result, seismic_result: dict | None = None,
                           wind_result: dict | None = None,
                           sbc_kN_m2: float = 150.0,
                           concrete: dict | None = None,
                           steel: dict | None = None) -> ComponentResult:
    """
    Convenience wrapper: pull column load, geometry and governing lateral effects
    from a TankDesignResult (+ seismic/wind dicts) and design the footing.
    """
    geo = result.geometry
    stg = result.reinforcement.get("staging", {})
    n = geo.get("n_columns", 6)
    P_col = stg.get("P_col_kN", result.cost_estimate.get("total", 0) and 0) or \
        stg.get("P_col_kN", 500.0)

    # column size
    col_size = (stg.get("col_dia_mm") or stg.get("col_size_mm") or 500) / 1000.0
    R_col = _column_ring_radius(result.tank_type, geo)

    # governing lateral load (max of seismic / wind)
    M_seis = (seismic_result or {}).get("M_ot_kNm", 0.0)
    V_seis = (seismic_result or {}).get("V_B_kN", 0.0)
    M_wind = (wind_result or {}).get("M_wind_kNm", 0.0)
    V_wind = (wind_result or {}).get("V_wind_kN", 0.0)
    M_ot = max(M_seis, M_wind)
    V_lat = max(V_seis, V_wind)

    # total vertical service load (water + structure)
    W_total = stg.get("W_total_kN", 0.0)
    if not W_total:
        W_total = P_col * n

    C = concrete or {"fck": 25, "sigma_cbc": 8.5, "m": 10.98}
    S = steel or {"sigma_st_b": 190.0}

    return design_foundation(
        P_col_service_kN=P_col, n_columns=n, R_col_m=R_col, col_size_m=col_size,
        M_ot_kNm=M_ot, V_lat_kN=V_lat, W_total_kN=W_total, sbc_kN_m2=sbc_kN_m2,
        concrete_grade_fck=C["fck"], sigma_cbc=C["sigma_cbc"],
        sigma_st=S.get("sigma_st_b", 190.0), m_modular=C["m"],
    )
