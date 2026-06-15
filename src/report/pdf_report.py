"""
pdf_report.py – Professional PDF design report for elevated RCC water tanks.
Uses ReportLab Platypus for multi-page layout with headers, tables, and formulas.
"""
from __future__ import annotations
import io, math, datetime, re
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable

from ..design.base import TankDesignResult

# ── Colour Palette ────────────────────────────────────────────────────────────
IS_BLUE  = colors.HexColor("#004B7F")
IS_GOLD  = colors.HexColor("#CC9900")
LT_BLUE  = colors.HexColor("#E8F1F8")
LT_GOLD  = colors.HexColor("#FFF8E1")
LT_GREY  = colors.HexColor("#F5F5F5")
MED_GREY = colors.HexColor("#CCCCCC")
RED      = colors.HexColor("#C0392B")
GREEN    = colors.HexColor("#27AE60")

W, H_PAGE = A4


# ── Custom Flowable: horizontal rule ─────────────────────────────────────────
class ISRule(Flowable):
    def __init__(self, width=None, thickness=1, color=IS_BLUE):
        super().__init__()
        self.width = width or (W - 30 * mm)
        self.thickness = thickness
        self.color = color
        self.height = thickness + 1

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


def _styles():
    ss = getSampleStyleSheet()
    base = dict(fontName="Helvetica", leading=14)
    bold = dict(fontName="Helvetica-Bold", leading=14)

    styles = {
        "title": ParagraphStyle("title", parent=ss["Title"],
                                textColor=IS_BLUE, fontSize=22,
                                fontName="Helvetica-Bold",
                                alignment=TA_CENTER, spaceAfter=4),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"],
                                   textColor=IS_GOLD, fontSize=12,
                                   fontName="Helvetica-Bold",
                                   alignment=TA_CENTER, spaceAfter=2),
        "h1": ParagraphStyle("h1", parent=ss["Heading1"],
                              textColor=IS_BLUE, fontSize=13,
                              fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4,
                              borderPad=4, borderColor=IS_BLUE, borderWidth=0,
                              backColor=LT_BLUE),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"],
                              textColor=IS_BLUE, fontSize=11,
                              fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", **base, fontSize=9,
                               alignment=TA_JUSTIFY, spaceAfter=4),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=8,
                               leading=11, textColor=colors.darkblue),
        "formula": ParagraphStyle("formula", fontName="Courier-Bold", fontSize=9,
                                  leading=12, textColor=IS_BLUE,
                                  backColor=LT_GREY, spaceAfter=4),
        "ok":   ParagraphStyle("ok",   **bold, textColor=GREEN, fontSize=9),
        "fail": ParagraphStyle("fail", **bold, textColor=RED, fontSize=9),
        "note": ParagraphStyle("note", **base, textColor=colors.darkgrey, fontSize=8,
                               leftIndent=8, spaceAfter=3),
        "th":   ParagraphStyle("th",   **bold, textColor=colors.white, fontSize=8,
                               alignment=TA_CENTER),
        "td":   ParagraphStyle("td",   **base, fontSize=8, alignment=TA_LEFT),
        "tdc":  ParagraphStyle("tdc",  **base, fontSize=8, alignment=TA_CENTER),
    }
    return styles


def _tbl_style(header_rows=1) -> TableStyle:
    cmds = [
        ("BACKGROUND",  (0, 0), (-1, header_rows - 1), IS_BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, header_rows - 1), colors.white),
        ("FONTNAME",    (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.4, MED_GREY),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, LT_GREY]),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]
    return TableStyle(cmds)


# ── Page Template callback ────────────────────────────────────────────────────
def _make_page_cb(title_short: str, project_name: str):
    def on_page(canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(IS_BLUE)
        canvas.rect(15 * mm, H_PAGE - 20 * mm, W - 30 * mm, 8 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(18 * mm, H_PAGE - 15 * mm, f"Elevated RCC Water Tank Design – {title_short}")
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(W - 16 * mm, H_PAGE - 15 * mm,
                               f"{project_name}  |  IS 3370:2009 / IS 456:2000")

        # Gold rule below header
        canvas.setStrokeColor(IS_GOLD)
        canvas.setLineWidth(1.2)
        canvas.line(15 * mm, H_PAGE - 21 * mm, W - 15 * mm, H_PAGE - 21 * mm)

        # Footer
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(15 * mm, 10 * mm,
                          f"Generated: {datetime.datetime.now().strftime('%d %b %Y  %H:%M')}")
        canvas.drawCentredString(W / 2, 10 * mm, f"Page {doc.page}")
        canvas.drawRightString(W - 15 * mm, 10 * mm, "Confidential – For Engineering Use Only")

        # Bottom blue bar
        canvas.setFillColor(IS_BLUE)
        canvas.rect(15 * mm, 6 * mm, W - 30 * mm, 2 * mm, fill=1, stroke=0)
        canvas.restoreState()
    return on_page


def _p(text, style): return Paragraph(str(text), style)
def _sp(n=6):        return Spacer(1, n * mm)


# ── Main report builder ───────────────────────────────────────────────────────
def generate_pdf_report(
    result: TankDesignResult,
    project_name: str = "EWT Project",
    location: str = "India",
    seismic_result: Optional[dict] = None,
    wind_result: Optional[dict] = None,
    ranked_types: Optional[list] = None,
    bbs_rows: Optional[list] = None,
    estimate_rows: Optional[list] = None,
    foundation_result=None,
) -> bytes:
    buf = io.BytesIO()
    ST = _styles()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=15 * mm,
        topMargin=28 * mm, bottomMargin=18 * mm,
        title=f"EWT Design Report – {project_name}",
        author="IS 3370:2009 Design Engine",
    )

    tank_short = result.tank_type.split("(")[0].strip()
    cb = _make_page_cb(tank_short, project_name)
    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        _sp(15),
        _p("DESIGN REPORT", ST["subtitle"]),
        _p("Elevated Reinforced Concrete Water Tank", ST["title"]),
        ISRule(thickness=2, color=IS_BLUE),
        ISRule(thickness=1, color=IS_GOLD),
        _sp(8),
    ]

    cover_data = [
        ["Project Name",    project_name],
        ["Location",        location],
        ["Tank Type",       result.tank_type],
        ["Capacity",        f"{result.capacity_m3:,.0f} m³"],
        ["Date",            datetime.datetime.now().strftime("%d %B %Y")],
        ["Design Code",     "IS 3370:2009 | IS 456:2000 | IS 875 | IS 1893 Part 2"],
        ["Design Method",   "Working Stress Method (WSM)"],
        ["Status",          "ADEQUATE" if result.ok else "NEEDS REVISION"],
    ]
    cw = [55 * mm, 115 * mm]
    tbl_cover = Table(cover_data, colWidths=cw)
    tbl_cover.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), LT_BLUE),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.5, MED_GREY),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND",  (1, 7), (1, 7),
         GREEN if result.ok else colors.HexColor("#FDECEA")),
        ("TEXTCOLOR",   (1, 7), (1, 7), GREEN if result.ok else RED),
        ("FONTNAME",    (1, 7), (1, 7), "Helvetica-Bold"),
    ]))
    story += [tbl_cover, _sp(6)]

    if result.warnings:
        story.append(_p("Design Notes / Warnings:", ST["h2"]))
        for w in result.warnings:
            story.append(_p(f"  &bull; {w}", ST["note"]))
        story.append(_sp(4))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1: TANK TYPE COMPARISON (if ranked)
    # ══════════════════════════════════════════════════════════════════════════
    if ranked_types:
        story.append(_p("1. Tank Type Optimisation & Selection", ST["h1"]))
        story.append(_p(
            "All feasible tank types were designed for the given capacity and site conditions. "
            "The optimum type is selected based on minimum cost per unit capacity and structural adequacy.",
            ST["body"]))
        story.append(_sp(3))

        hdr = [["Rank", "Tank Type", "Volume\n(m³)", "Cost/m³\n(Rs.)", "Concrete\n(m³)",
                "Steel\n(kg)", "Design\nOK", "Recommendation"]]
        rows = hdr[:]
        for i, (nm, res, sc) in enumerate(ranked_types):
            rows.append([
                f"#{i + 1}", nm,
                f"{res.volumes.get('total_concrete_m3', 0):.1f}",
                f"Rs.{sc['cost_per_m3']:,.0f}",
                f"{res.volumes.get('total_concrete_m3', 0):.1f}",
                f"{res.volumes.get('total_steel_kg', 0):.0f}",
                "OK" if res.ok else "Revise",
                re.sub(r"[^\x00-\x7f]", "", sc["recommendation"]).strip()[:32],
            ])

        cws = [12*mm, 32*mm, 18*mm, 22*mm, 18*mm, 15*mm, 12*mm, 45*mm]
        t = Table(rows, colWidths=cws)
        t.setStyle(_tbl_style(1))
        # Highlight best
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 1), (-1, 1), LT_GOLD),
            ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
        ]))
        story += [t, _sp(4), PageBreak()]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2: GEOMETRY & INPUT
    # ══════════════════════════════════════════════════════════════════════════
    story.append(_p("2. Input Parameters & Tank Geometry", ST["h1"]))
    geo = result.geometry
    geo_data = [[_lp(_pretty(k)[0], ST["td"]), _lp(_val_unit(k, v), ST["tdc"])]
                for k, v in geo.items()]
    t_geo = Table([["Parameter", "Value"]] + geo_data, colWidths=[80*mm, 90*mm])
    t_geo.setStyle(_tbl_style(1))
    story += [t_geo, _sp(6)]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3: COMPONENT-WISE DESIGN
    # ══════════════════════════════════════════════════════════════════════════
    story.append(_p("3. Component-Wise Design Calculations", ST["h1"]))

    for comp in result.components:
        tag = "[OK]" if comp.ok else "[CHECK]"
        story.append(_p(f"{tag}  {comp.name}", ST["h2"]))
        if comp.warnings:
            for w in comp.warnings:
                story.append(_p(f"  &bull; {w}", ST["note"]))

        if comp.details:
            d_rows = [["Parameter", "Value", "Unit"]]
            for k, v in comp.details.items():
                label, unit = _pretty(k)
                d_rows.append([_lp(label, ST["td"]), _lp(_fmt(v), ST["tdc"]),
                               _lp(unit or "&ndash;", ST["tdc"])])
            t_comp = Table(d_rows, colWidths=[80*mm, 50*mm, 40*mm])
            t_comp.setStyle(_tbl_style(1))
            story.append(KeepTogether([t_comp, _sp(4)]))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4: SEISMIC & WIND
    # ══════════════════════════════════════════════════════════════════════════
    if seismic_result or wind_result:
        story.append(_p("4. Seismic & Wind Analysis", ST["h1"]))

    if seismic_result:
        story.append(_p("4.1  Seismic Design — IS 1893 Part 2:2016 Two-Mass Model", ST["h2"]))
        story.append(_p(
            "The elevated tank is modelled as a two-degree-of-freedom system with "
            "impulsive (mi) and convective (mc) liquid masses per IS 1893 Part 2.", ST["body"]))
        s_rows = [["Parameter", "Value"]]
        for k, v in seismic_result.items():
            s_rows.append([_lp(_pretty(k)[0], ST["td"]), _lp(_val_unit(k, v), ST["tdc"])])
        t_s = Table(s_rows, colWidths=[90*mm, 80*mm])
        t_s.setStyle(_tbl_style(1))
        story += [t_s, _sp(4)]

    if wind_result:
        story.append(_p("4.2  Wind Force — IS 875 Part 3:2015", ST["h2"]))
        w_rows = [["Parameter", "Value"]]
        for k, v in wind_result.items():
            w_rows.append([_lp(_pretty(k)[0], ST["td"]), _lp(_val_unit(k, v), ST["tdc"])])
        t_w = Table(w_rows, colWidths=[90*mm, 80*mm])
        t_w.setStyle(_tbl_style(1))
        story += [t_w, _sp(4)]

    if foundation_result is not None:
        story.append(_p("4.3  Foundation & Global Stability — IS 456:2000", ST["h2"]))
        status = "ADEQUATE" if foundation_result.ok else "NEEDS REVISION"
        story.append(_p(
            f"Isolated square footing per staging column (Working Stress Method); "
            f"bearing checked against soil SBC, footing depth governed by punching "
            f"shear (cl. B-5). Overturning and sliding factors of safety computed "
            f"for the governing lateral load. Status: <b>{status}</b>.", ST["body"]))
        if foundation_result.warnings:
            for w in foundation_result.warnings:
                story.append(_p(f"  &bull; {w}", ST["note"]))
        f_rows = [["Parameter", "Value"]]
        for k, v in foundation_result.details.items():
            f_rows.append([_lp(_pretty(k)[0], ST["td"]), _lp(_val_unit(k, v), ST["tdc"])])
        t_f = Table(f_rows, colWidths=[90*mm, 80*mm])
        t_f.setStyle(_tbl_style(1))
        story += [t_f, _sp(4)]

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5: REINFORCEMENT SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    story.append(_p("5. Reinforcement Summary", ST["h1"]))
    rw_hdr = [["Component", "Steel Type", "Dia (mm)", "Spacing\n(mm)", "Ast Reqd\n(mm²/m)", "Ast Prov\n(mm²/m)"]]
    rw = rw_hdr[:]
    for k, v in result.reinforcement.items():
        if not isinstance(v, dict):
            continue
        # Extract bar info
        dia   = v.get("bar_dia") or v.get("hoop_bar_dia") or v.get("vert_bar_dia") or "—"
        sp    = v.get("bar_spacing_mm") or v.get("hoop_spacing_mm") or v.get("spacing") or "—"
        ast_r = (v.get("Ast_hoop_mm2_per_m") or v.get("Ast_mm2_per_m") or
                 v.get("Ast_mer_mm2_per_m") or v.get("Ast_mrb_mm2") or "—")
        ast_p = v.get("Ast_prov") or v.get("Ast_hoop_prov") or "—"
        rw.append([k.replace("_", " ").title(), "HYSD", _fmt(dia), _fmt(sp), _fmt(ast_r), _fmt(ast_p)])

    t_rw = Table(rw, colWidths=[50*mm, 25*mm, 20*mm, 20*mm, 28*mm, 28*mm])
    t_rw.setStyle(_tbl_style(1))
    story += [t_rw, _sp(6), PageBreak()]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6: BAR BENDING SCHEDULE
    # ══════════════════════════════════════════════════════════════════════════
    if bbs_rows or result.bbs:
        story.append(_p("6. Bar Bending Schedule (BBS)", ST["h1"]))
        story.append(_p(
            "Unit weight = d² / 162.2 kg/m (where d = bar dia in mm). "
            "Lengths include standard hooks and laps per IS 2502.", ST["body"]))
        bbs = bbs_rows or result.bbs
        bbs_hdr = [["Mark", "Location", "Dia\n(mm)", "Shape", "Cut Len\n(m)", "Nos",
                    "Total Len\n(m)", "Weight\n(kg)"]]
        bbs_data = bbs_hdr[:]
        total_wt = 0.0
        for row in bbs:
            bbs_data.append([
                row.get("mark", ""), row.get("location", ""),
                row.get("dia_mm", ""), row.get("shape", ""),
                row.get("cut_length_m", ""), row.get("nos", ""),
                row.get("total_length_m", ""), row.get("weight_kg", ""),
            ])
            total_wt += float(row.get("weight_kg", 0))

        bbs_data.append(["", "TOTAL", "", "", "", "", "", f"{total_wt:.1f} kg"])

        cws_bbs = [15*mm, 42*mm, 12*mm, 22*mm, 17*mm, 12*mm, 17*mm, 18*mm]
        t_bbs = Table(bbs_data, colWidths=cws_bbs, repeatRows=1)
        t_bbs.setStyle(_tbl_style(1))
        t_bbs.setStyle(TableStyle([
            ("BACKGROUND", (0, len(bbs_data) - 1), (-1, -1), LT_GOLD),
            ("FONTNAME",   (0, len(bbs_data) - 1), (-1, -1), "Helvetica-Bold"),
        ]))
        story += [t_bbs, _sp(6), PageBreak()]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7: COST ESTIMATE
    # ══════════════════════════════════════════════════════════════════════════
    story.append(_p("7. Abstract of Cost Estimate", ST["h1"]))
    story.append(_p("Based on DSR 2023-24 rates (indicative; for detailed estimate use BOQ).", ST["body"]))

    vol = result.volumes
    ce  = result.cost_estimate

    est_hdr = [["#", "Item of Work", "Qty", "Unit", "Rate (Rs.)", "Amount (Rs.)"]]
    items = [
        ("01", "Concrete for tank walls (incl. formwork & curing)", vol.get("concrete_wall_m3", 0), "m³", 8000),
        ("02", "Concrete for domes / roof",
         vol.get("concrete_dome_m3", vol.get("concrete_top_dome_m3", 0)) +
         vol.get("concrete_bottom_dome_m3", 0) + vol.get("concrete_cone_m3", 0), "m³", 8500),
        ("03", "Concrete for floor slab",
         vol.get("concrete_floor_m3", 0), "m³", 7500),
        ("04", "Concrete for ring beams / girder",
         vol.get("concrete_rings_m3", vol.get("concrete_brb_m3", 0)), "m³", 8000),
        ("05", "Concrete for staging columns",
         vol.get("concrete_columns_m3", 0), "m³", 7500),
        ("06", "Steel reinforcement (supply & place)",
         vol.get("total_steel_kg", 0), "kg", 75),
        ("07", "Waterproofing (2-coat epoxy, water face)",
         round(3.14159 * result.geometry.get("D_int_m", 5) *
               result.geometry.get("H_water_m", result.geometry.get("H_cylinder_m", 3)), 1),
         "m²", 350),
        ("08", "MS ladder, access platform, manhole",
         1, "LS", round(ce.get("total", 0) * 0.02)),
        ("09", "Foundation (isolated/raft; assumed)",
         1, "LS", round(ce.get("total", 0) * 0.12)),
        ("10", "Water testing & commissioning",
         result.capacity_m3, "m³", 50),
    ]

    est_data = est_hdr[:]
    sub_total = 0.0
    for item in items:
        no, desc, qty, unit, rate = item
        amt = float(qty) * float(rate)
        sub_total += amt
        est_data.append([no, desc, f"{qty:.1f}", unit, f"Rs.{rate:,.0f}", f"Rs.{amt:,.0f}"])

    cont = sub_total * 0.05
    gst  = (sub_total + cont) * 0.18
    grand = sub_total + cont + gst

    est_data += [
        ["", "Sub-Total", "", "", "", f"Rs.{sub_total:,.0f}"],
        ["", "Contingency @ 5%", "", "", "", f"Rs.{cont:,.0f}"],
        ["", "GST @ 18%", "", "", "", f"Rs.{gst:,.0f}"],
        ["", "GRAND TOTAL", "", "", "", f"Rs.{grand:,.0f}"],
    ]

    cws_est = [12*mm, 65*mm, 18*mm, 12*mm, 22*mm, 28*mm]
    t_est = Table(est_data, colWidths=cws_est, repeatRows=1)
    t_est.setStyle(_tbl_style(1))
    n = len(est_data)
    t_est.setStyle(TableStyle([
        ("BACKGROUND", (0, n - 4), (-1, n - 4), LT_GREY),
        ("BACKGROUND", (0, n - 3), (-1, n - 3), LT_GREY),
        ("BACKGROUND", (0, n - 2), (-1, n - 2), LT_GREY),
        ("BACKGROUND", (0, n - 1), (-1, n - 1), IS_BLUE),
        ("TEXTCOLOR",  (0, n - 1), (-1, n - 1), colors.white),
        ("FONTNAME",   (0, n - 1), (-1, n - 1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, n - 1), (-1, n - 1), 9),
    ]))
    story += [t_est, _sp(6)]

    # ── Remarks ────────────────────────────────────────────────────────────────
    story.append(_p("8. Code References & Notes", ST["h1"]))
    refs = [
        "IS 3370 (Part I–IV):2009 – Concrete structures for storage of liquids",
        "IS 456:2000 – Plain & Reinforced Concrete – Code of Practice",
        "IS 875 (Part 1–3):1987/2015 – Dead, Live & Wind Loads",
        "IS 1893 (Part 2):2016 – Seismic design of liquid retaining tanks",
        "SP 16:1980 – Design Aids for Reinforced Concrete to IS 456",
        "All calculations are based on Working Stress Method (WSM) as mandated by IS 3370.",
        "Minimum concrete grade: M25 for liquid-retaining members (IS 3370 Part I, cl. 4).",
        "Cover to water face: 45 mm; other face: 25 mm (IS 3370 Part I, cl. 4.1).",
        "Permissible crack width: 0.1 mm (severe) / 0.2 mm (moderate) – IS 3370 Part I, cl. 8.1.",
        "This report is for preliminary/detailed design; independent verification is recommended.",
    ]
    for i, ref in enumerate(refs):
        story.append(_p(f"  [{i + 1}]  {ref}", ST["note"]))

    # Build PDF
    doc.build(story, onFirstPage=cb, onLaterPages=cb)
    return buf.getvalue()


# ── Helpers: professional unit + label rendering (super/subscripts) ───────────
def _fmt(v):
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 100 else f"{v:,.1f}"
    return str(v)


# Trailing unit token in a result key -> ReportLab inline markup.
# Longest / most specific suffixes are listed first.
_UNIT_SUFFIX = [
    ("kNm_per_m", "kN&middot;m/m"),
    ("kN_per_m",  "kN/m"),
    ("kN_m2",     "kN/m<super>2</super>"),
    ("N_mm2",     "N/mm<super>2</super>"),
    ("mm2_per_m", "mm<super>2</super>/m"),
    ("kg_m3",     "kg/m<super>3</super>"),
    ("m_s",       "m/s"),
    ("kNm",       "kN&middot;m"),
    ("mm2",       "mm<super>2</super>"),
    ("m3",        "m<super>3</super>"),
    ("m2",        "m<super>2</super>"),
    ("kN",        "kN"),
    ("mm",        "mm"),
    ("deg",       "&deg;"),
    ("sec",       "s"),
    ("kg",        "kg"),
    ("m",         "m"),
    ("t",         "t"),
]


def _split_unit(key: str):
    """Return (stem_without_unit, unit_markup_or_None)."""
    low = key.lower()
    for suf, mk in _UNIT_SUFFIX:
        if low.endswith("_" + suf.lower()):
            return key[: -(len(suf) + 1)], mk
    return key, None


# Clean, professional labels (ASCII only so Helvetica renders them);
# subscripts/superscripts via ReportLab <sub>/<super>.
_LABEL = {
    # geometry
    "d_int": "Internal diameter, D", "r_int": "Internal radius, R",
    "h_water": "Water depth, H", "h_total": "Overall height",
    "h_cylinder": "Cylinder height, H<sub>c</sub>",
    "h_cone": "Conical dome height, H<sub>cone</sub>",
    "free_board": "Free board", "actual_vol": "Provided capacity",
    "staging_height": "Staging height", "n_columns": "Number of columns",
    "cone_angle": "Cone angle", "d1": "Cone bottom dia, d<sub>1</sub>",
    "r_bot_dome": "Bottom dome radius, R<sub>b</sub>",
    "h_s": "Bottom dome rise", "theta_bot": "Bottom dome half-angle",
    # wall
    "thickness": "Thickness", "h2_dt_param": "H<super>2</super>/Dt parameter",
    "t_hoop_max": "Max hoop tension, T<sub>hoop</sub>",
    "m_base": "Base moment, M<sub>base</sub>",
    "ast_hoop": "Hoop steel, A<sub>st</sub>",
    "hoop_bar_dia": "Hoop bar dia", "hoop_spacing": "Hoop spacing",
    "ast_hoop_prov": "Hoop steel provided",
    "ast_vert": "Vertical steel, A<sub>st</sub>",
    "vert_bar_dia": "Vertical bar dia", "vert_spacing": "Vertical spacing",
    "ast_vert_prov": "Vertical steel provided",
    # domes / rings
    "rise": "Rise", "rd": "Dome radius, R<sub>d</sub>", "theta": "Half-angle",
    "w0": "Design load, w<sub>0</sub>", "n_phi": "Meridional thrust, N",
    "t_dome": "Dome thickness", "ast_dome": "Dome steel, A<sub>st</sub>",
    "dome_bar_dia": "Dome bar dia", "dome_bar_spacing": "Dome bar spacing",
    "t_top_ring": "Top-ring tension, T", "ast_top_ring": "Top-ring steel, A<sub>st</sub>",
    "top_ring_dia": "Top-ring bar dia", "top_ring_spacing": "Top-ring spacing",
    "n_phi_cone": "Cone meridional thrust, N", "h_comp_cone": "Cone horizontal thrust",
    "t_mrb": "Ring-beam tension, T", "ast_mrb": "Ring-beam steel, A<sub>st</sub>",
    "slant_length": "Slant length", "t_cone": "Cone thickness",
    "n_phi_base": "Meridional thrust (base), N", "n_theta_base": "Hoop force (base)",
    "ast_meridional": "Meridional steel, A<sub>st</sub>",
    "ast_mer": "Meridional steel, A<sub>st</sub>",
    "mer_bar_dia": "Meridional bar dia", "mer_spacing": "Meridional spacing",
    # floor / generic beam
    "p_floor": "Floor pressure", "m_centre": "Centre moment, M",
    "ast": "Steel, A<sub>st</sub>", "bar_dia": "Bar dia", "bar_spacing": "Bar spacing",
    "ast_prov": "Steel provided", "b": "Width, b", "d": "Depth, d",
    "w_total": "Total load, W", "m": "Moment, M", "p": "Pressure",
    # staging
    "col_dia": "Column diameter", "col_size": "Column size",
    "l_eff": "Effective length, L<sub>eff</sub>", "lambda": "Slenderness ratio",
    "slenderness_ratio": "Slenderness ratio", "p_col": "Column load, P",
    "n_long_bars": "No. of longitudinal bars", "long_bar_dia": "Longitudinal bar dia",
    "ast_col": "Column steel, A<sub>st</sub>",
    # intze checks / girder
    "h_outward_cone": "Outward thrust (cone)", "h_inward_dome": "Inward thrust (dome)",
    "t_net_brb": "Net ring force, T<sub>net</sub>", "intze_balanced": "Intze balanced?",
    "m_midspan": "Mid-span moment, M", "t_torsion": "Torsion, T",
    "w_per_m": "UDL on girder, w", "ast_ring_tension": "Ring-tension steel, A<sub>st</sub>",
    "ast_main": "Main steel, A<sub>st</sub>", "n_stirrups": "No. of stirrups",
    # seismic
    "zone": "Seismic zone", "z": "Zone factor, Z", "i": "Importance factor, I",
    "r": "Response factor, R", "h_d_ratio": "h/D ratio",
    "mi_m": "Impulsive mass ratio, m<sub>i</sub>/m",
    "mc_m": "Convective mass ratio, m<sub>c</sub>/m",
    "mi": "Impulsive mass, m<sub>i</sub>", "mc": "Convective mass, m<sub>c</sub>",
    "ms": "Structural mass, m<sub>s</sub>",
    "t_i": "Impulsive period, T<sub>i</sub>", "t_c": "Convective period, T<sub>c</sub>",
    "sa_i_g": "S<sub>a</sub>/g (impulsive)", "sa_c_g": "S<sub>a</sub>/g (convective)",
    "ah_i": "Design coeff., A<sub>h,i</sub>", "ah_c": "Design coeff., A<sub>h,c</sub>",
    "v_i": "Impulsive shear, V<sub>i</sub>", "v_c": "Convective shear, V<sub>c</sub>",
    "v_b": "Base shear, V<sub>B</sub>", "m_i": "Impulsive moment, M<sub>i</sub>",
    "m_c": "Convective moment, M<sub>c</sub>", "m_ot": "Overturning moment, M<sub>ot</sub>",
    "lateral_stiffness": "Lateral stiffness, K<sub>s</sub>",
    # wind
    "vz": "Design wind speed, V<sub>z</sub>", "pz": "Wind pressure, p<sub>z</sub>",
    "f_tank": "Force on tank, F<sub>tank</sub>", "f_staging": "Force on staging, F<sub>stg</sub>",
    "v_wind": "Wind base shear, V", "m_wind": "Wind moment, M",
    # foundation
    "p_col_service": "Service column load, P", "dp_overturning": "Overturning increment",
    "p_max": "Max column load, P<sub>max</sub>", "p_min": "Min column load, P<sub>min</sub>",
    "footing_size": "Footing size (square)", "footing_thickness": "Footing thickness",
    "eff_depth": "Effective depth, d", "bearing_pressure": "Bearing pressure",
    "sbc_allow": "Allowable SBC", "m_face": "Moment at column face, M",
    "dev_length": "Development length, L<sub>d</sub>",
    "punching_tau_perm": "Punching shear (allowable)", "oneway_tau": "One-way shear stress",
    "fos_overturning": "FoS, overturning", "fos_sliding": "FoS, sliding",
    "uplift": "Net uplift?",
}


def _pretty(key: str):
    """Return (label_markup, unit_markup_or_None) for a result key."""
    stem, unit = _split_unit(key)
    low = stem.lower()
    if low in _LABEL:
        label = _LABEL[low]
    else:
        label = stem.replace("_", " ").strip().title()
        label = re.sub(r"\bAst\b", "A<sub>st</sub>", label)
        label = re.sub(r"\bFck\b", "f<sub>ck</sub>", label)
    # a few keys carry an implied unit not encoded in the suffix
    if unit is None:
        if "spacing" in low or low.endswith("dia"):
            unit = "mm"
    return label, unit


def _lp(text, style):
    """Paragraph cell that interprets <super>/<sub> markup."""
    return Paragraph(str(text), style)


def _val_unit(key, v):
    """Value cell text with its unit appended as markup."""
    _, unit = _pretty(key)
    return f"{_fmt(v)} {unit}" if unit else _fmt(v)
