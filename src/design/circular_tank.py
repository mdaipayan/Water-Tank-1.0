"""
circular_tank.py – Design engine for Circular (Cylindrical) Elevated RCC Water Tank.
References: IS 3370:2009 Parts I, II, IV; IS 456:2000; IS 875 Part 3
"""
from __future__ import annotations
import math
from .base import (CONCRETE, STEEL, GAMMA_W, GAMMA_RCC, COVER_WATER_FACE,
                   choose_bar, neutral_axis, lever_arm, min_ast,
                   ast_from_moment, ast_from_tension,
                   ComponentResult, TankDesignResult)
from .is3370_tables import get_ct_cm


def design_circular_tank(
    capacity_m3: float,
    H_D_ratio: float = 0.5,
    concrete_grade: str = "M25",
    steel_grade: str = "Fe415",
    free_board_m: float = 0.3,
    staging_height_m: float = 12.0,
    n_columns: int = 6,
) -> TankDesignResult:
    """
    Full WSM design of a circular flat-bottom elevated tank per IS 3370:2009.
    Returns a TankDesignResult with all components, reinforcement, and BBS.
    """
    result = TankDesignResult(
        tank_type="Circular (Cylindrical) Flat-Bottom",
        capacity_m3=capacity_m3,
    )
    C = CONCRETE[concrete_grade]
    S = STEEL[steel_grade]
    fck       = C["fck"]
    sigma_cbc = C["sigma_cbc"]
    m         = C["m"]
    sigma_st  = S["sigma_st_b"]
    sigma_std = S["sigma_st_d"]

    # ── Geometry ──────────────────────────────────────────────────────────────
    # V = π/4 D² H  →  D = (4V / (π H/D))^(1/3)  since H = H_D_ratio × D
    D = (4 * capacity_m3 / (math.pi * H_D_ratio)) ** (1 / 3)
    D = math.ceil(D * 4) / 4            # round up to nearest 250 mm
    H_water = H_D_ratio * D
    H_water = round(H_water * 4) / 4    # 250 mm multiples
    actual_vol = math.pi / 4 * D ** 2 * H_water
    H_total = H_water + free_board_m
    R = D / 2

    result.geometry = {
        "D_int_m": round(D, 3),
        "R_int_m": round(R, 3),
        "H_water_m": round(H_water, 3),
        "H_total_m": round(H_total, 3),
        "actual_vol_m3": round(actual_vol, 2),
        "free_board_m": free_board_m,
        "staging_height_m": staging_height_m,
        "n_columns": n_columns,
    }

    # ── Cylindrical Wall Design ───────────────────────────────────────────────
    comp = ComponentResult("Cylindrical Wall")

    # Trial wall thickness
    t_wall = max(H_water / 30, 0.20)     # IS 3370 min
    t_wall = math.ceil(t_wall * 20) / 20  # round to 50 mm

    # IS 3370 Pt IV coefficients depend on liquid depth H_water (not freeboard)
    ct, cm, param = get_ct_cm(H_water, D, t_wall)

    # Critical hoop tension (maximum over height)  T = Ct * γw * H * R  [kN/m]
    T_hoop_max = max(ct) * GAMMA_W * H_water * R
    T_hoop_vals = [c * GAMMA_W * H_water * R for c in ct]

    # Critical BM   M = Cm * γw * H³  [kN·m/m]
    M_wall_vals = [c * GAMMA_W * H_water ** 3 for c in cm]
    M_wall_max  = max(abs(v) for v in M_wall_vals)
    M_base      = abs(cm[-1]) * GAMMA_W * H_water ** 3

    # Effective depth of wall
    cover = COVER_WATER_FACE
    d_wall = t_wall * 1000 - cover - 8   # mm

    # Hoop steel (circumferential) – direct tension
    Ast_hoop = ast_from_tension(T_hoop_max, sigma_std)
    Ast_hoop = max(Ast_hoop, min_ast(t_wall * 1000, steel_grade))
    hoop_bar = choose_bar(Ast_hoop / 2, 150)  # divide for 2 faces
    Ast_hoop_prov = 2 * hoop_bar["Ast_prov"]  # total over both faces

    # Vertical steel – bending
    Ast_vert = ast_from_moment(M_base, d_wall, sigma_st, m, sigma_cbc)
    Ast_vert = max(Ast_vert, min_ast(t_wall * 1000, steel_grade))
    vert_bar = choose_bar(Ast_vert, 150)

    comp.details = {
        "thickness_mm": int(t_wall * 1000),
        "H2_Dt_param": param,
        "T_hoop_max_kN_per_m": round(T_hoop_max, 2),
        "M_base_kNm_per_m": round(M_base, 3),
        "Ast_hoop_mm2_per_m": round(Ast_hoop, 1),
        "hoop_bar_dia": hoop_bar["dia"],
        "hoop_spacing_mm": hoop_bar["spacing"],
        "Ast_hoop_prov": round(Ast_hoop_prov, 1),
        "Ast_vert_mm2_per_m": round(Ast_vert, 1),
        "vert_bar_dia": vert_bar["dia"],
        "vert_spacing_mm": vert_bar["spacing"],
        "Ast_vert_prov": vert_bar["Ast_prov"],
    }
    if Ast_hoop_prov < Ast_hoop:
        comp.fail(f"Hoop steel deficient: prov={Ast_hoop_prov:.0f} < req={Ast_hoop:.0f} mm²/m")
    result.add(comp)
    result.reinforcement["wall"] = comp.details

    # ── Top Dome (Roof) ────────────────────────────────────────────────────────
    comp = ComponentResult("Top Dome (Roof)")
    rise_d = D / 5
    Rd     = (R ** 2 + rise_d ** 2) / (2 * rise_d)
    sin_th = R / Rd
    cos_th = math.sqrt(1 - sin_th ** 2)
    theta  = math.asin(sin_th)

    DL_dome = 0.1 * GAMMA_RCC           # self-weight assuming 100 mm dome
    LL_dome = 1.5                         # kN/m²  IS 875 Part 2
    w0_dome = DL_dome + LL_dome

    N_phi_dome = w0_dome * Rd / (1 + cos_th)   # kN/m meridional thrust
    N_theta_dome_edge = w0_dome * Rd * (1 - 1 / (1 + cos_th))  # hoop at edge

    t_dome = max(N_phi_dome / (0.45 * fck * 1000) * 1e3, 100)   # mm
    t_dome = math.ceil(t_dome / 10) * 10

    Ast_dome = max(0.3 / 100 * t_dome * 1000, 200)   # nominal IS 3370 min
    dome_bar = choose_bar(Ast_dome, 200)

    # Top ring beam – hoop tension from dome thrust
    T_top_ring = N_phi_dome * cos_th * R   # kN
    Ast_top_ring = ast_from_tension(T_top_ring, sigma_std)
    top_ring_bar = choose_bar(Ast_top_ring, 150)

    comp.details = {
        "rise_m": round(rise_d, 3),
        "Rd_m": round(Rd, 3),
        "theta_deg": round(math.degrees(theta), 2),
        "w0_kN_m2": round(w0_dome, 2),
        "N_phi_kN_per_m": round(N_phi_dome, 2),
        "t_dome_mm": int(t_dome),
        "Ast_dome_mm2_per_m": round(Ast_dome, 1),
        "dome_bar_dia": dome_bar["dia"],
        "dome_bar_spacing": dome_bar["spacing"],
        "T_top_ring_kN": round(T_top_ring, 2),
        "Ast_top_ring": round(Ast_top_ring, 1),
        "top_ring_dia": top_ring_bar["dia"],
        "top_ring_spacing": top_ring_bar["spacing"],
    }
    result.add(comp)
    result.reinforcement["top_dome"] = comp.details

    # ── Floor Slab (Flat Circular) ────────────────────────────────────────────
    comp = ComponentResult("Flat Floor Slab")
    # Circular plate simply supported on ring beam
    p_floor = GAMMA_W * H_water + GAMMA_RCC * 0.25    # water + slab sw (assumed 250mm)
    # Max BM at centre of circular plate: M = p R² (3+ν) / 16, ν=0.2
    nu = 0.2
    M_floor = p_floor * R ** 2 * (3 + nu) / 16  # kN·m/m
    t_floor = max(R / 8, 0.20)                   # rough sizing
    t_floor = math.ceil(t_floor * 20) / 20
    d_floor = t_floor * 1000 - COVER_WATER_FACE - 10

    Ast_floor = ast_from_moment(M_floor, d_floor, sigma_st, m, sigma_cbc)
    Ast_floor = max(Ast_floor, min_ast(t_floor * 1000, steel_grade))
    floor_bar = choose_bar(Ast_floor, 150)

    comp.details = {
        "thickness_mm": int(t_floor * 1000),
        "p_floor_kN_m2": round(p_floor, 2),
        "M_centre_kNm_per_m": round(M_floor, 3),
        "Ast_mm2_per_m": round(Ast_floor, 1),
        "bar_dia": floor_bar["dia"],
        "bar_spacing_mm": floor_bar["spacing"],
        "Ast_prov": floor_bar["Ast_prov"],
    }
    result.add(comp)
    result.reinforcement["floor_slab"] = comp.details

    # ── Bottom Ring Beam ───────────────────────────────────────────────────────
    comp = ComponentResult("Bottom Ring Beam")
    # Carries wall reaction + floor slab; distribute to staging
    total_water_wt = GAMMA_W * actual_vol
    wall_wt = GAMMA_RCC * math.pi * D * H_total * t_wall
    dome_wt = GAMMA_RCC * (2 * math.pi * Rd * rise_d) * (t_dome / 1000)
    floor_wt = GAMMA_RCC * (math.pi / 4 * D ** 2) * t_floor
    W_total_kN = total_water_wt + wall_wt + dome_wt + floor_wt

    # Hoop tension in bottom ring beam (from inclined component if any)
    # For vertical wall, mainly BM+axial; assume T_brb negligible for flat floor
    T_brb = 0.0
    brb_b = max(0.30, t_wall + 0.05)   # m
    brb_d = max(0.60, D / 10)           # m
    Mbrb   = W_total_kN / (n_columns) * (2 * math.pi * R / n_columns) / 8
    d_brb  = brb_d * 1000 - 50
    Ast_brb = ast_from_moment(Mbrb, d_brb, sigma_st, m, sigma_cbc)
    Ast_brb = max(Ast_brb, 0.24 / 100 * brb_b * 1000 * brb_d * 1000)
    brb_bar = choose_bar(Ast_brb, 150)

    comp.details = {
        "b_mm": int(brb_b * 1000),
        "d_mm": int(brb_d * 1000),
        "W_total_kN": round(W_total_kN, 1),
        "M_kNm": round(Mbrb, 2),
        "Ast_mm2": round(Ast_brb, 1),
        "bar_dia": brb_bar["dia"],
        "bar_spacing": brb_bar["spacing"],
    }
    result.add(comp)
    result.reinforcement["bottom_ring_beam"] = comp.details

    # ── Staging ───────────────────────────────────────────────────────────────
    comp = ComponentResult("Staging Columns & Bracings")
    col_dia = max(0.45, D / 8)
    col_dia = round(col_dia * 4) / 4

    P_col = W_total_kN / n_columns + W_total_kN * 0.15  # + staging DL estimate
    # Effective length for staging column (IS 456 cl. 25)
    L_eff = 0.85 * staging_height_m
    # Check slenderness ratio l_eff / D_col <= 60
    lambda_col = L_eff / col_dia
    if lambda_col > 60:
        comp.fail(f"Column slenderness l/D={lambda_col:.1f} > 60 – increase column dia")

    # Ag required
    Ag_req = P_col * 1000 / (0.45 * fck + 0.75 * S["fy"] * 0.02)  # mm²  approx
    col_dia_req = math.sqrt(4 * Ag_req / math.pi) / 1000  # m
    if col_dia < col_dia_req:
        col_dia = math.ceil(col_dia_req * 4) / 4
        comp.warn(f"Column diameter revised to {col_dia*1000:.0f} mm")

    # Longitudinal steel in column: 1-2% of Ag
    Ag = math.pi / 4 * (col_dia * 1000) ** 2
    Ast_col = max(0.012 * Ag, 6 * BAR_AREA_16)   # ≥6 bars of 16
    col_bars = max(6, round(Ast_col / BAR_AREA_16))

    comp.details = {
        "col_dia_mm": int(col_dia * 1000),
        "L_eff_m": round(L_eff, 2),
        "lambda": round(lambda_col, 1),
        "P_col_kN": round(P_col, 1),
        "n_long_bars": col_bars,
        "long_bar_dia": 16,
    }
    result.add(comp)
    result.reinforcement["staging"] = comp.details

    # ── Volume / Cost Estimate ────────────────────────────────────────────────
    _vol_concrete_wall  = math.pi * D * H_total * t_wall                     # m³
    _vol_concrete_dome  = 2 * math.pi * Rd * rise_d * (t_dome / 1000)       # m³
    _vol_concrete_floor = math.pi / 4 * D ** 2 * t_floor                    # m³
    _vol_concrete_brb   = 2 * math.pi * R * brb_b * brb_d                   # m³
    _vol_concrete_col   = n_columns * math.pi / 4 * col_dia ** 2 * staging_height_m
    V_conc_total = (_vol_concrete_wall + _vol_concrete_dome +
                    _vol_concrete_floor + _vol_concrete_brb + _vol_concrete_col)

    # Steel estimate: approx 1.2% of concrete volume by weight (typical)
    rho_steel = 7850   # kg/m³
    W_steel_kg = V_conc_total * 0.012 * rho_steel   # rough estimate

    RATE_CONC = 7500   # ₹/m³ (M25 including formwork, placing)
    RATE_STEE = 75     # ₹/kg
    RATE_MISC = 1.15   # contingency + misc (15%)

    cost_concrete = V_conc_total * RATE_CONC
    cost_steel    = W_steel_kg   * RATE_STEE
    cost_total    = (cost_concrete + cost_steel) * RATE_MISC

    result.volumes = {
        "concrete_wall_m3": round(_vol_concrete_wall, 2),
        "concrete_dome_m3": round(_vol_concrete_dome, 2),
        "concrete_floor_m3": round(_vol_concrete_floor, 2),
        "concrete_brb_m3": round(_vol_concrete_brb, 2),
        "concrete_columns_m3": round(_vol_concrete_col, 2),
        "total_concrete_m3": round(V_conc_total, 2),
        "total_steel_kg": round(W_steel_kg, 0),
    }
    result.cost_estimate = {
        "concrete_cost": round(cost_concrete),
        "steel_cost": round(cost_steel),
        "total": round(cost_total),
        "cost_per_m3_capacity": round(cost_total / capacity_m3),
    }

    # ── BBS stub (full BBS generated in bbs.py) ───────────────────────────────
    result.bbs = _build_bbs(result, D, H_total, H_water, t_wall, t_dome, t_floor,
                             brb_b, brb_d, staging_height_m, n_columns, col_dia)

    return result


BAR_AREA_16 = 201.06   # mm²

# ──────────────────────────────────────────────────────────────────────────────

def _build_bbs(result, D, H_total, H_water, t_wall, t_dome, t_floor,
               brb_b, brb_d, staging_height_m, n_columns, col_dia):
    """Build bar-bending schedule rows for circular tank."""
    bbs = []
    wr = result.reinforcement

    def _row(mark, loc, dia, shape, length_m, nos, weight_per_m=None):
        if weight_per_m is None:
            weight_per_m = dia ** 2 / 162.2   # kg/m
        total_len = nos * length_m
        weight = total_len * weight_per_m
        bbs.append({
            "mark": mark,
            "location": loc,
            "dia_mm": dia,
            "shape": shape,
            "cut_length_m": round(length_m, 3),
            "nos": nos,
            "total_length_m": round(total_len, 3),
            "weight_kg": round(weight, 2),
        })

    circ = math.pi * D
    wall = wr.get("wall", {})

    # Hoop bars in wall (2 faces)
    n_hoop_rings = int(H_total / (wall.get("hoop_spacing_mm", 150) / 1000)) + 1
    bar_len_hoop = circ + 0.60   # lap + hooks
    _row("W1", "Wall – Hoop (outer)", wall.get("hoop_bar_dia", 12),
         "Straight (ring)", bar_len_hoop, n_hoop_rings * 2)

    # Vertical bars
    sp_v = wall.get("vert_spacing_mm", 150) / 1000
    n_vert = int(math.pi * D / sp_v)
    bar_len_vert = H_total + 0.50
    _row("W2", "Wall – Vertical", wall.get("vert_bar_dia", 12),
         "Straight", bar_len_vert, n_vert * 2)

    # Dome nominal
    dome = wr.get("top_dome", {})
    n_dome_rings = int((D / 2) / (dome.get("dome_bar_spacing", 200) / 1000)) + 1
    for i, ring_D in enumerate([D * f for f in [0.2, 0.4, 0.6, 0.8, 1.0]]):
        ring_len = math.pi * ring_D + 0.40
        _row(f"D{i+1}", "Dome – Circumferential", dome.get("dome_bar_dia", 10),
             "Circular ring", ring_len, 2)

    # Floor radial + circumferential
    floor = wr.get("floor_slab", {})
    n_rad  = int(math.pi * D / (floor.get("bar_spacing_mm", 150) / 1000))
    _row("F1", "Floor – Radial", floor.get("bar_dia", 12), "Straight",
         D / 2 + 0.30, n_rad)
    n_circ_f = int((D / 2) / (floor.get("bar_spacing_mm", 150) / 1000)) + 1
    for i in range(n_circ_f):
        r_f = (i + 0.5) * (D / 2) / n_circ_f
        _row(f"F2-{i+1}", "Floor – Circumferential", floor.get("bar_dia", 12),
             "Ring", math.pi * 2 * r_f + 0.40, 2)

    # Bottom ring beam
    brb = wr.get("bottom_ring_beam", {})
    n_brb_bars = max(4, int((2 * math.pi * D / 2) / 0.20))
    _row("B1", "Bottom Ring Beam – Main", brb.get("bar_dia", 16),
         "Straight (ring)", math.pi * D + 0.60, 4)
    n_stirrups = int(2 * math.pi * D / 2 / 0.20) + 1
    _row("B2", "Bottom Ring Beam – Stirrups",
         10, "Rectangular stirrup",
         2 * (brb_b * 1000 + brb_d * 1000) / 1000 + 0.20, n_stirrups)

    # Staging columns
    stg = wr.get("staging", {})
    col_long_len  = staging_height_m + 0.80
    col_lat_pitch = 0.20
    n_ties = int(staging_height_m / col_lat_pitch) + 1
    for c in range(n_columns):
        _row(f"C{c+1}L", f"Col {c+1} – Longitudinal",
             stg.get("long_bar_dia", 16), "Straight",
             col_long_len, stg.get("n_long_bars", 8))
        _row(f"C{c+1}T", f"Col {c+1} – Ties",
             8, "Circular ring",
             math.pi * col_dia + 0.30, n_ties)

    return bbs
