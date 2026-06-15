"""
intze_tank.py – WSM design of Intze Elevated RCC Water Tank.
References: IS 3370:2009 Parts I, II, IV; IS 456:2000
"""
from __future__ import annotations
import math
from .base import (CONCRETE, STEEL, GAMMA_W, GAMMA_RCC, COVER_WATER_FACE,
                   choose_bar, neutral_axis, lever_arm, min_ast,
                   ast_from_moment, ast_from_tension,
                   ComponentResult, TankDesignResult)
from .is3370_tables import get_ct_cm


def design_intze_tank(
    capacity_m3: float,
    H_D_ratio: float  = 0.5,
    concrete_grade: str = "M25",
    steel_grade: str    = "Fe415",
    cone_angle_deg: float = 45.0,
    staging_height_m: float = 12.0,
    n_columns: int = 6,
    free_board_m: float = 0.3,
) -> TankDesignResult:
    """
    Full WSM design of an Intze elevated tank per IS 3370:2009.
    Components: top dome → cylindrical wall → middle ring beam →
                conical dome → bottom spherical dome → bottom ring girder → staging
    """
    result = TankDesignResult(
        tank_type="Intze Tank",
        capacity_m3=capacity_m3,
    )
    C = CONCRETE[concrete_grade]
    S = STEEL[steel_grade]
    fck        = C["fck"]
    sigma_cbc  = C["sigma_cbc"]
    m_mod      = C["m"]
    sigma_st   = S["sigma_st_b"]
    sigma_std  = S["sigma_st_d"]
    alpha_rad  = math.radians(cone_angle_deg)

    # ── Geometry ───────────────────────────────────────────────────────────────
    # First, estimate total volume accounting for all components
    # Iterate: assume Vc (cylinder) ≈ 0.70 * V_total
    V_cyl_frac = 0.70
    # Cylinder: V_cyl = π/4 D² H_c  with H_c = H_D_ratio * D
    D = (4 * capacity_m3 * V_cyl_frac / (math.pi * H_D_ratio)) ** (1 / 3)
    D = math.ceil(D * 4) / 4
    H_c = H_D_ratio * D
    H_c = round(H_c * 4) / 4
    R   = D / 2

    # Conical dome: from D down to d1 = D/2 (typical)
    d1 = D / 2          # diameter at bottom of cone
    r1 = d1 / 2         # radius at bottom of cone
    H_cone = (R - r1) / math.tan(alpha_rad)

    # Bottom spherical dome: rise = d1/6
    h_s  = d1 / 6
    R_bot = (r1 ** 2 + h_s ** 2) / (2 * h_s)   # radius of bottom dome
    theta_bot = math.asin(r1 / R_bot)
    cos_theta_bot = math.cos(theta_bot)

    # Volumes
    V_cyl   = math.pi / 4 * D ** 2 * H_c
    V_cone  = (math.pi / 3) * (R ** 2 + R * r1 + r1 ** 2) * H_cone
    V_bdome = math.pi * h_s ** 2 * (R_bot - h_s / 3)
    actual_vol = V_cyl + V_cone - V_bdome

    # Scale up D if volume insufficient
    if actual_vol < capacity_m3 * 0.99:
        scale = (capacity_m3 / actual_vol) ** (1 / 3)
        D = math.ceil(D * scale * 4) / 4
        H_c = H_D_ratio * D
        H_c = round(H_c * 4) / 4
        R   = D / 2
        d1  = D / 2
        r1  = d1 / 2
        H_cone = (R - r1) / math.tan(alpha_rad)
        h_s  = d1 / 6
        R_bot = (r1 ** 2 + h_s ** 2) / (2 * h_s)
        theta_bot = math.asin(r1 / R_bot)
        cos_theta_bot = math.cos(theta_bot)
        V_cyl   = math.pi / 4 * D ** 2 * H_c
        V_cone  = (math.pi / 3) * (R ** 2 + R * r1 + r1 ** 2) * H_cone
        V_bdome = math.pi * h_s ** 2 * (R_bot - h_s / 3)
        actual_vol = V_cyl + V_cone - V_bdome

    H_total = H_c + free_board_m

    result.geometry = {
        "D_int_m": round(D, 3),
        "R_int_m": round(R, 3),
        "H_cylinder_m": round(H_c, 3),
        "H_cone_m": round(H_cone, 3),
        "cone_angle_deg": round(cone_angle_deg, 1),
        "d1_m": round(d1, 3),
        "R_bot_dome_m": round(R_bot, 3),
        "h_s_m": round(h_s, 3),
        "theta_bot_deg": round(math.degrees(theta_bot), 2),
        "actual_vol_m3": round(actual_vol, 2),
        "staging_height_m": staging_height_m,
        "n_columns": n_columns,
    }

    # ══ 1. TOP DOME ════════════════════════════════════════════════════════════
    comp = ComponentResult("Top Dome (Roof)")
    rise_td = D / 5
    Rd_top  = (R ** 2 + rise_td ** 2) / (2 * rise_td)
    sin_th  = R / Rd_top
    cos_th  = math.sqrt(1 - sin_th ** 2)
    theta_top = math.asin(sin_th)

    DL_td = 0.10 * GAMMA_RCC
    LL_td = 1.5
    w0_td = DL_td + LL_td

    N_phi_td = w0_td * Rd_top / (1 + cos_th)        # kN/m
    N_th_td  = w0_td * Rd_top * (1 - 1 / (1 + cos_th))
    t_td     = max(int(N_phi_td / (0.45 * fck) * 1000 / 10 + 1) * 10, 100)

    Ast_td = max(0.3 / 100 * t_td * 1000, 200)
    bar_td = choose_bar(Ast_td, 200)

    T_top_ring = N_phi_td * cos_th * R
    Ast_trb = ast_from_tension(T_top_ring, sigma_std)
    bar_trb  = choose_bar(Ast_trb, 150)
    trb_b = 0.30; trb_d = 0.40

    comp.details = {
        "rise_m": round(rise_td, 3), "Rd_m": round(Rd_top, 3),
        "theta_deg": round(math.degrees(theta_top), 2),
        "N_phi_kN_per_m": round(N_phi_td, 2),
        "t_mm": t_td, "Ast_mm2_per_m": round(Ast_td, 1),
        "bar_dia": bar_td["dia"], "bar_spacing": bar_td["spacing"],
        "T_top_ring_kN": round(T_top_ring, 2),
        "Ast_top_ring_mm2": round(Ast_trb, 1),
        "top_ring_bar_dia": bar_trb["dia"],
        "trb_b_mm": int(trb_b * 1000), "trb_d_mm": int(trb_d * 1000),
    }
    result.add(comp)
    result.reinforcement["top_dome"] = comp.details

    # ══ 2. CYLINDRICAL WALL ═══════════════════════════════════════════════════
    comp = ComponentResult("Cylindrical Wall")
    t_wall = max(H_c / 30, 0.20)
    t_wall = math.ceil(t_wall * 20) / 20

    ct, cm, param = get_ct_cm(H_c, D, t_wall)
    T_hoop_max = max(ct) * GAMMA_W * H_c * R
    M_base_wall = abs(cm[-1]) * GAMMA_W * H_c ** 3

    cover = COVER_WATER_FACE
    d_wall = t_wall * 1000 - cover - 8

    Ast_hoop = ast_from_tension(T_hoop_max, sigma_std)
    Ast_hoop = max(Ast_hoop, min_ast(t_wall * 1000, steel_grade))
    hoop_bar = choose_bar(Ast_hoop / 2, 150)

    Ast_vert = ast_from_moment(M_base_wall, d_wall, sigma_st, m_mod, sigma_cbc)
    Ast_vert = max(Ast_vert, min_ast(t_wall * 1000, steel_grade))
    vert_bar = choose_bar(Ast_vert, 150)

    comp.details = {
        "thickness_mm": int(t_wall * 1000),
        "H2_Dt_param": param,
        "T_hoop_max_kN_per_m": round(T_hoop_max, 2),
        "M_base_kNm_per_m": round(M_base_wall, 3),
        "Ast_hoop_mm2_per_m": round(Ast_hoop, 1),
        "hoop_bar_dia": hoop_bar["dia"],
        "hoop_spacing_mm": hoop_bar["spacing"],
        "Ast_vert_mm2_per_m": round(Ast_vert, 1),
        "vert_bar_dia": vert_bar["dia"],
        "vert_spacing_mm": vert_bar["spacing"],
    }
    result.add(comp)
    result.reinforcement["wall"] = comp.details

    # ══ 3. MIDDLE RING BEAM (cylinder–cone junction) ══════════════════════════
    comp = ComponentResult("Middle Ring Beam")
    # Water pressure at bottom of cylinder (top of cone)
    p_mid = GAMMA_W * H_c  # kN/m²
    # Meridional force in cone at top
    slant_len = (R - r1) / math.sin(alpha_rad)
    w_cone_sw = GAMMA_RCC * 0.15   # per m² of cone surface (assumed 150 mm)
    N_phi_cone_top = (p_mid * R + w_cone_sw * slant_len) / (2 * math.sin(alpha_rad))
    H_comp_cone = N_phi_cone_top * math.cos(alpha_rad)   # outward horizontal thrust from cone

    # Net hoop tension in middle ring beam
    T_mrb = H_comp_cone * R
    Ast_mrb = ast_from_tension(T_mrb, sigma_std)
    mrb_b = max(0.35, t_wall + 0.05)
    mrb_d = max(0.50, T_mrb / (0.45 * fck * mrb_b * 1000) * 1000 / 1000 + 0.20)
    bar_mrb = choose_bar(Ast_mrb / 2, 150)

    comp.details = {
        "N_phi_cone_kN_per_m": round(N_phi_cone_top, 2),
        "H_comp_cone_kN_per_m": round(H_comp_cone, 2),
        "T_mrb_kN": round(T_mrb, 2),
        "Ast_mrb_mm2": round(Ast_mrb, 1),
        "bar_dia": bar_mrb["dia"],
        "bar_spacing": bar_mrb["spacing"],
        "b_mm": int(mrb_b * 1000),
        "d_mm": int(mrb_d * 1000),
    }
    result.add(comp)
    result.reinforcement["middle_ring_beam"] = comp.details

    # ══ 4. CONICAL DOME ════════════════════════════════════════════════════════
    comp = ComponentResult("Conical Dome")
    # At bottom of cone (largest stresses)
    p_base_cone = GAMMA_W * (H_c + H_cone)   # max water pressure
    r_base_cone = r1

    N_phi_cone_base = (p_base_cone * r_base_cone + w_cone_sw * slant_len) / \
                      (2 * math.sin(alpha_rad))
    N_theta_cone_base = p_base_cone * r_base_cone / math.sin(alpha_rad)

    t_cone = max(N_phi_cone_base / (0.45 * fck * 1000) * 1e3, 150)
    t_cone = math.ceil(t_cone / 10) * 10

    Ast_cone_mer  = ast_from_tension(N_phi_cone_base,  sigma_std)
    Ast_cone_hoop = ast_from_tension(N_theta_cone_base, sigma_std)
    Ast_cone_mer  = max(Ast_cone_mer,  min_ast(t_cone, steel_grade))
    Ast_cone_hoop = max(Ast_cone_hoop, min_ast(t_cone, steel_grade))
    bar_cone_mer  = choose_bar(Ast_cone_mer,  150)
    bar_cone_hoop = choose_bar(Ast_cone_hoop, 150)

    comp.details = {
        "t_cone_mm": int(t_cone),
        "slant_length_m": round(slant_len, 3),
        "N_phi_base_kN_per_m": round(N_phi_cone_base, 2),
        "N_theta_base_kN_per_m": round(N_theta_cone_base, 2),
        "Ast_meridional_mm2_per_m": round(Ast_cone_mer, 1),
        "mer_bar_dia": bar_cone_mer["dia"],
        "mer_spacing_mm": bar_cone_mer["spacing"],
        "Ast_hoop_mm2_per_m": round(Ast_cone_hoop, 1),
        "hoop_bar_dia": bar_cone_hoop["dia"],
        "hoop_spacing_mm": bar_cone_hoop["spacing"],
    }
    result.add(comp)
    result.reinforcement["conical_dome"] = comp.details

    # ══ 5. BOTTOM SPHERICAL DOME ══════════════════════════════════════════════
    comp = ComponentResult("Bottom Spherical Dome")
    # Loads: self-weight + water pressure
    p_bot_dome_avg = GAMMA_W * (H_c + H_cone + h_s / 2)
    t_bdome = max(150, int(r1 * 1000 / 10))   # mm

    w0_bd = GAMMA_RCC * (t_bdome / 1000) + p_bot_dome_avg
    N_phi_bd = w0_bd * R_bot / (1 + cos_theta_bot)
    N_th_bd  = w0_bd * R_bot * (math.cos(theta_bot) - 1 / (1 + cos_theta_bot))

    Ast_bd_mer  = max(ast_from_tension(N_phi_bd,  sigma_std), min_ast(t_bdome, steel_grade))
    Ast_bd_hoop = max(ast_from_tension(abs(N_th_bd), sigma_std), min_ast(t_bdome, steel_grade))
    bar_bd_mer  = choose_bar(Ast_bd_mer,  200)
    bar_bd_hoop = choose_bar(Ast_bd_hoop, 200)

    comp.details = {
        "t_mm": t_bdome,
        "R_bot_m": round(R_bot, 3),
        "theta_deg": round(math.degrees(theta_bot), 2),
        "N_phi_kN_per_m": round(N_phi_bd, 2),
        "N_theta_kN_per_m": round(N_th_bd, 2),
        "Ast_mer_mm2_per_m": round(Ast_bd_mer, 1),
        "mer_bar_dia": bar_bd_mer["dia"],
        "mer_spacing_mm": bar_bd_mer["spacing"],
        "Ast_hoop_mm2_per_m": round(Ast_bd_hoop, 1),
        "hoop_bar_dia": bar_bd_hoop["dia"],
        "hoop_spacing_mm": bar_bd_hoop["spacing"],
    }
    result.add(comp)
    result.reinforcement["bottom_dome"] = comp.details

    # ══ 6. INTZE CONDITION VERIFICATION ═══════════════════════════════════════
    comp = ComponentResult("Intze Condition Verification")
    H_out_cone  = N_phi_cone_base * math.cos(alpha_rad)         # outward
    H_in_dome   = N_phi_bd * math.cos(math.acos(cos_theta_bot))  # inward = N_phi × sin(theta_bot) × cos component
    H_in_dome2  = N_phi_bd * math.sin(theta_bot)

    T_brb_net = (H_out_cone - H_in_dome2) * r1    # kN, net hoop force in bottom ring beam
    intze_ok  = abs(T_brb_net) < 0.15 * H_out_cone * r1 + 10

    if not intze_ok:
        comp.warn(f"Intze condition not perfectly balanced: T_net={T_brb_net:.1f} kN. "
                  f"Residual hoop tension in bottom ring beam.")

    comp.details = {
        "H_outward_cone_kN_per_m": round(H_out_cone, 2),
        "H_inward_dome_kN_per_m": round(H_in_dome2, 2),
        "T_net_brb_kN": round(T_brb_net, 2),
        "intze_balanced": intze_ok,
    }
    result.add(comp)
    result.reinforcement["intze_check"] = comp.details

    # ══ 7. BOTTOM RING GIRDER (Circular Beam) ═════════════════════════════════
    comp = ComponentResult("Bottom Ring Girder (Circular Beam)")
    # Total superstructure load
    W_water = GAMMA_W * actual_vol
    W_wall  = GAMMA_RCC * math.pi * D * H_total * t_wall
    W_tdome = GAMMA_RCC * 2 * math.pi * Rd_top * rise_td * (t_td / 1000)
    W_cone  = GAMMA_RCC * math.pi * (R + r1) * slant_len * (t_cone / 1000)
    W_bdome = GAMMA_RCC * 2 * math.pi * R_bot * h_s * (t_bdome / 1000)
    W_rings = GAMMA_RCC * (trb_b * trb_d * 2 * math.pi * R +
                            mrb_b * mrb_d * 2 * math.pi * R)
    W_total = W_water + W_wall + W_tdome + W_cone + W_bdome + W_rings

    R_girder = R   # radius of ring girder centre line ≈ R
    w_uniform = W_total / (2 * math.pi * R_girder)   # kN/m uniformly distributed on ring beam

    # Timoshenko / IS 456 approach for circular beam with n equally-spaced supports
    # BM at mid-span and torsion
    n = n_columns
    phi = math.pi / n
    # Max BM at midspan
    M_midspan = w_uniform * R_girder ** 2 * (0.5 / math.tan(phi) - 1 / (2 * phi))
    # Max torsion
    T_tor = w_uniform * R_girder ** 2 * (0.5 - phi / (2 * math.sin(phi)) * math.cos(phi))
    T_tor = abs(T_tor)

    brg_b = max(0.40, D / 5)
    brg_d = max(0.70, abs(M_midspan) / (sigma_cbc * brg_b * 1000 * 0.35) * 1000 / 1000)
    brg_b = round(brg_b * 4) / 4
    brg_d = round(brg_d * 4) / 4
    d_brg = brg_d * 1000 - 50

    # Main steel for BM
    Ast_brg = ast_from_moment(abs(M_midspan), d_brg, sigma_st, m_mod, sigma_cbc)
    # Additional torsion steel (simplified)
    Ast_tor = (T_tor * 1e6) / (sigma_std * brg_b * 1000)
    # Tension-ring steel: the bottom ring girder must also resist the residual
    # (un-balanced) horizontal thrust from the Intze condition as hoop tension.
    Ast_ring_tension = ast_from_tension(abs(T_brb_net), sigma_std)
    Ast_brg_total = Ast_brg + Ast_tor + Ast_ring_tension
    bar_brg = choose_bar(Ast_brg_total, 150)

    n_stirrups_brg = int(2 * math.pi * R_girder / 0.20) + 1

    comp.details = {
        "b_mm": int(brg_b * 1000), "d_mm": int(brg_d * 1000),
        "W_total_kN": round(W_total, 1),
        "w_per_m_kN": round(w_uniform, 2),
        "M_midspan_kNm": round(M_midspan, 2),
        "T_torsion_kNm": round(T_tor, 2),
        "Ast_ring_tension_mm2": round(Ast_ring_tension, 1),
        "Ast_main_mm2": round(Ast_brg_total, 1),
        "bar_dia": bar_brg["dia"],
        "bar_spacing": bar_brg["spacing"],
        "n_stirrups": n_stirrups_brg,
    }
    result.add(comp)
    result.reinforcement["ring_girder"] = comp.details

    # ══ 8. STAGING COLUMNS ════════════════════════════════════════════════════
    comp = ComponentResult("Staging Columns")
    col_dia = max(0.50, D / 8)
    col_dia = round(col_dia * 4) / 4
    P_col = (W_total + GAMMA_RCC * n_columns * math.pi / 4 * col_dia ** 2
             * staging_height_m) / n_columns
    L_eff = 0.85 * staging_height_m
    lam = L_eff / col_dia
    if lam > 60:
        comp.fail(f"Slenderness l/D={lam:.1f}>60; increase column dia or add bracings")
    Ag = math.pi / 4 * (col_dia * 1000) ** 2
    p_steel = max(0.012, P_col * 1000 / (0.45 * fck * Ag) - 0.45 * fck / (0.75 * S["fy"]))
    p_steel = min(p_steel, 0.04)
    Ast_col = p_steel * Ag
    n_bars  = max(6, round(Ast_col / 314.16))   # using 20mm bars approx

    comp.details = {
        "col_dia_mm": int(col_dia * 1000),
        "L_eff_m": round(L_eff, 2),
        "slenderness_ratio": round(lam, 1),
        "P_col_kN": round(P_col, 1),
        "n_long_bars": n_bars,
        "bar_dia_mm": 20,
        "Ast_col_mm2": round(Ast_col, 0),
    }
    result.add(comp)
    result.reinforcement["staging"] = comp.details

    # ══ VOLUMES & COST ═══════════════════════════════════════════════════════
    Vc_wall  = math.pi * D * H_total * t_wall
    Vc_tdome = 2 * math.pi * Rd_top * rise_td * (t_td / 1000)
    Vc_cone  = math.pi * (R + r1) * slant_len * (t_cone / 1000)
    Vc_bdome = 2 * math.pi * R_bot * h_s * (t_bdome / 1000)
    Vc_rings = (trb_b * trb_d * 2 * math.pi * R +
                mrb_b * mrb_d * 2 * math.pi * R +
                brg_b * brg_d * 2 * math.pi * R_girder)
    Vc_cols  = n_columns * math.pi / 4 * col_dia ** 2 * staging_height_m
    Vc_total = Vc_wall + Vc_tdome + Vc_cone + Vc_bdome + Vc_rings + Vc_cols

    W_steel_kg = Vc_total * 0.013 * 7850

    RATE_CONC = 8000;  RATE_STEE = 75;  MISC = 1.15
    cost_conc  = Vc_total * RATE_CONC
    cost_steel = W_steel_kg * RATE_STEE
    cost_total = (cost_conc + cost_steel) * MISC

    result.volumes = {
        "concrete_wall_m3": round(Vc_wall, 2),
        "concrete_top_dome_m3": round(Vc_tdome, 2),
        "concrete_cone_m3": round(Vc_cone, 2),
        "concrete_bottom_dome_m3": round(Vc_bdome, 2),
        "concrete_rings_m3": round(Vc_rings, 2),
        "concrete_columns_m3": round(Vc_cols, 2),
        "total_concrete_m3": round(Vc_total, 2),
        "total_steel_kg": round(W_steel_kg, 0),
    }
    result.cost_estimate = {
        "concrete_cost": round(cost_conc),
        "steel_cost": round(cost_steel),
        "total": round(cost_total),
        "cost_per_m3_capacity": round(cost_total / capacity_m3),
    }

    result.bbs = _build_intze_bbs(result, D, H_c, H_total, t_wall, t_td, t_cone, t_bdome,
                                   r1, R_bot, slant_len, staging_height_m, n_columns,
                                   col_dia, brg_b, brg_d)
    return result


def _build_intze_bbs(result, D, H_c, H_total, t_wall, t_td, t_cone, t_bdome,
                      r1, R_bot, slant_len, staging_height_m, n_columns,
                      col_dia, brg_b, brg_d):
    bbs = []
    wr = result.reinforcement

    def row(mark, loc, dia, shape, cut_m, nos):
        bbs.append({
            "mark": mark, "location": loc, "dia_mm": dia, "shape": shape,
            "cut_length_m": round(cut_m, 3), "nos": nos,
            "total_length_m": round(cut_m * nos, 3),
            "weight_kg": round(cut_m * nos * dia ** 2 / 162.2, 2),
        })

    R = D / 2
    wall = wr.get("wall", {})
    circ = math.pi * D

    # Wall hoop bars
    n_h = int(H_total / (wall.get("hoop_spacing_mm", 150) / 1000)) + 1
    row("W1", "Wall Hoop (2 faces)", wall.get("hoop_bar_dia", 12), "Ring", circ + 0.60, n_h * 2)
    # Wall vertical
    sp_v = wall.get("vert_spacing_mm", 150) / 1000
    n_v  = int(circ / sp_v)
    row("W2", "Wall Vertical (2 faces)", wall.get("vert_bar_dia", 12), "Straight",
        H_total + 0.50, n_v * 2)

    # Top dome rings
    dome = wr.get("top_dome", {})
    for i, frac in enumerate([0.2, 0.4, 0.6, 0.8, 1.0]):
        row(f"TD{i+1}", "Top Dome Ring", dome.get("bar_dia", 10), "Ring",
            math.pi * D * frac + 0.40, 2)

    # Top ring beam bars
    row("TRB1", "Top Ring Beam – Main", dome.get("top_ring_bar_dia", 12),
        "Ring", circ + 0.60, 4)

    # Middle ring beam
    mrb = wr.get("middle_ring_beam", {})
    row("MRB1", "Middle Ring Beam – Main", mrb.get("bar_dia", 16),
        "Ring", circ + 0.60, 4)
    n_mrb_stir = int(circ / 0.20) + 1
    row("MRB2", "Middle Ring Beam – Stirrups", 10, "Closed stirrup",
        2 * (mrb.get("b_mm", 350) + mrb.get("d_mm", 500)) / 1000 + 0.20, n_mrb_stir)

    # Conical dome: along slope & circumferential
    cone = wr.get("conical_dome", {})
    n_cone_hoop = int(slant_len / (cone.get("hoop_spacing_mm", 150) / 1000)) + 1
    for i in range(6):
        r_i = r1 + (R - r1) * i / 5
        row(f"CD{i+1}", "Cone Hoop", cone.get("hoop_bar_dia", 12),
            "Ring", math.pi * 2 * r_i + 0.40, 2)
    n_mer = int(math.pi * D / (cone.get("mer_spacing_mm", 150) / 1000))
    row("CDM", "Cone Meridional", cone.get("mer_bar_dia", 12),
        "Straight", slant_len + 0.40, n_mer * 2)

    # Bottom dome
    bdome = wr.get("bottom_dome", {})
    for i, frac in enumerate([0.2, 0.4, 0.6, 0.8, 1.0]):
        row(f"BD{i+1}", "Bot Dome Ring", bdome.get("hoop_bar_dia", 10),
            "Ring", math.pi * 2 * r1 * frac + 0.40, 2)
    n_mer_bd = int(math.pi * 2 * r1 / (bdome.get("mer_spacing_mm", 200) / 1000))
    row("BDM", "Bot Dome Meridional", bdome.get("mer_bar_dia", 10),
        "Straight", R_bot * math.radians(math.degrees(math.asin(r1 / R_bot))) + 0.30, n_mer_bd)

    # Ring girder
    rg = wr.get("ring_girder", {})
    row("RG1", "Ring Girder – Main Bot", rg.get("bar_dia", 20),
        "Ring", math.pi * D + 0.60, 4)
    row("RG2", "Ring Girder – Main Top", rg.get("bar_dia", 20),
        "Ring", math.pi * D + 0.60, 2)
    n_rg_st = rg.get("n_stirrups", 50)
    row("RG3", "Ring Girder – Stirrups", 10, "Closed stirrup",
        2 * (brg_b + brg_d) + 0.30, n_rg_st)

    # Staging columns
    stg = wr.get("staging", {})
    for c in range(n_columns):
        row(f"SC{c+1}L", f"Col {c+1} Longitudinal",
            stg.get("bar_dia_mm", 20), "Straight",
            staging_height_m + 0.80, stg.get("n_long_bars", 8))
        n_ties = int(staging_height_m / 0.20) + 1
        row(f"SC{c+1}T", f"Col {c+1} Ties",
            8, "Circular ring", math.pi * col_dia + 0.30, n_ties)

    return bbs
