"""
rectangular_tank.py – WSM design of Rectangular Elevated RCC Water Tank.
References: IS 3370:2009 Parts I, II, IV; IS 456:2000
"""
from __future__ import annotations
import math
from .base import (CONCRETE, STEEL, GAMMA_W, GAMMA_RCC, COVER_WATER_FACE,
                   choose_bar, ast_from_moment, ast_from_tension, min_ast,
                   ComponentResult, TankDesignResult)
from .is3370_tables import get_rect_coeffs


def design_rectangular_tank(
    capacity_m3: float,
    L_B_ratio: float = 1.5,
    concrete_grade: str = "M25",
    steel_grade: str = "Fe415",
    free_board_m: float = 0.3,
    staging_height_m: float = 10.0,
    n_columns: int = 4,
) -> TankDesignResult:
    result = TankDesignResult(
        tank_type="Rectangular Tank",
        capacity_m3=capacity_m3,
    )
    C = CONCRETE[concrete_grade]
    S = STEEL[steel_grade]
    fck       = C["fck"]
    sigma_cbc = C["sigma_cbc"]
    m_mod     = C["m"]
    sigma_st  = S["sigma_st_b"]
    sigma_std = S["sigma_st_d"]

    # ── Geometry ──────────────────────────────────────────────────────────────
    # V = L × B × H  with L = L_B_ratio × B, H ≈ 0.5*(L+B)/2 (typical)
    B = (capacity_m3 / (L_B_ratio * 0.5 * (L_B_ratio + 1))) ** (1 / 3)
    B = math.ceil(B * 4) / 4
    L = round(L_B_ratio * B * 4) / 4
    H_w = round(capacity_m3 / (L * B) * 4) / 4
    actual_vol = L * B * H_w
    H_total = H_w + free_board_m

    result.geometry = {
        "L_m": round(L, 3), "B_m": round(B, 3),
        "H_water_m": round(H_w, 3), "H_total_m": round(H_total, 3),
        "actual_vol_m3": round(actual_vol, 2),
        "staging_height_m": staging_height_m,
        "n_columns": n_columns,
    }

    # ── Long Wall ─────────────────────────────────────────────────────────────
    comp = ComponentResult("Long Wall")
    t_lw = max(H_w / 30, 0.15)
    t_lw = math.ceil(t_lw * 20) / 20
    p0   = GAMMA_W * H_w
    ax, ay_b, ay_m = get_rect_coeffs(L, H_w)

    Mx_lw = ax * p0 * L ** 2      # horizontal BM (kN·m/m)
    My_lw_base = ay_b * p0 * H_w ** 2  # vertical BM at base
    My_lw_mid  = ay_m * p0 * H_w ** 2

    d_lw = t_lw * 1000 - COVER_WATER_FACE - 8
    Ast_h = max(ast_from_moment(Mx_lw, d_lw, sigma_st, m_mod, sigma_cbc),
                min_ast(t_lw * 1000, steel_grade))
    Ast_v = max(ast_from_moment(My_lw_base, d_lw, sigma_st, m_mod, sigma_cbc),
                min_ast(t_lw * 1000, steel_grade))
    bar_h = choose_bar(Ast_h, 150)
    bar_v = choose_bar(Ast_v, 150)

    comp.details = {
        "thickness_mm": int(t_lw * 1000),
        "Mx_kNm_per_m": round(Mx_lw, 3),
        "My_base_kNm_per_m": round(My_lw_base, 3),
        "Ast_horiz_mm2_per_m": round(Ast_h, 1),
        "horiz_bar_dia": bar_h["dia"], "horiz_spacing_mm": bar_h["spacing"],
        "Ast_vert_mm2_per_m": round(Ast_v, 1),
        "vert_bar_dia": bar_v["dia"], "vert_spacing_mm": bar_v["spacing"],
    }
    result.add(comp); result.reinforcement["long_wall"] = comp.details

    # ── Short Wall ────────────────────────────────────────────────────────────
    comp = ComponentResult("Short Wall")
    t_sw = max(H_w / 30, 0.15)
    t_sw = math.ceil(t_sw * 20) / 20
    ax_s, ay_b_s, _ = get_rect_coeffs(B, H_w)

    Mx_sw = ax_s * p0 * B ** 2
    My_sw = ay_b_s * p0 * H_w ** 2
    d_sw  = t_sw * 1000 - COVER_WATER_FACE - 8
    Ast_h_s = max(ast_from_moment(Mx_sw, d_sw, sigma_st, m_mod, sigma_cbc),
                  min_ast(t_sw * 1000, steel_grade))
    Ast_v_s = max(ast_from_moment(My_sw, d_sw, sigma_st, m_mod, sigma_cbc),
                  min_ast(t_sw * 1000, steel_grade))
    bar_h_s = choose_bar(Ast_h_s, 150)
    bar_v_s = choose_bar(Ast_v_s, 150)

    comp.details = {
        "thickness_mm": int(t_sw * 1000),
        "Mx_kNm_per_m": round(Mx_sw, 3), "My_base_kNm_per_m": round(My_sw, 3),
        "Ast_horiz_mm2_per_m": round(Ast_h_s, 1),
        "horiz_bar_dia": bar_h_s["dia"], "horiz_spacing_mm": bar_h_s["spacing"],
        "Ast_vert_mm2_per_m": round(Ast_v_s, 1),
        "vert_bar_dia": bar_v_s["dia"], "vert_spacing_mm": bar_v_s["spacing"],
    }
    result.add(comp); result.reinforcement["short_wall"] = comp.details

    # ── Roof Slab ─────────────────────────────────────────────────────────────
    comp = ComponentResult("Roof Slab")
    t_roof = max(L / 25, 0.12)
    t_roof = math.ceil(t_roof * 20) / 20
    w_roof = GAMMA_RCC * t_roof + 1.5
    lx = min(L, B); ly = max(L, B)
    r = ly / lx
    alpha_x_r = 0.084 / (1 + (r / 2) ** 4) * max(r ** 2, 1)   # simplified
    M_roof_x = alpha_x_r * w_roof * lx ** 2
    d_r = t_roof * 1000 - 25 - 8
    Ast_roof = max(ast_from_moment(M_roof_x, d_r, sigma_st, m_mod, sigma_cbc),
                   0.12 / 100 * t_roof * 1000 * 1000)
    bar_rf = choose_bar(Ast_roof, 150)
    comp.details = {
        "thickness_mm": int(t_roof * 1000),
        "M_kNm_per_m": round(M_roof_x, 3),
        "Ast_mm2_per_m": round(Ast_roof, 1),
        "bar_dia": bar_rf["dia"], "bar_spacing_mm": bar_rf["spacing"],
    }
    result.add(comp); result.reinforcement["roof_slab"] = comp.details

    # ── Floor Slab ────────────────────────────────────────────────────────────
    comp = ComponentResult("Floor Slab")
    t_fl = max(0.20, L / 20)
    t_fl = math.ceil(t_fl * 20) / 20
    p_fl = GAMMA_W * H_w + GAMMA_RCC * t_fl
    M_fl = p_fl * B ** 2 / 12    # continuous slab approx
    d_fl = t_fl * 1000 - COVER_WATER_FACE - 10
    Ast_fl = max(ast_from_moment(M_fl, d_fl, sigma_st, m_mod, sigma_cbc),
                 min_ast(t_fl * 1000, steel_grade))
    bar_fl = choose_bar(Ast_fl, 150)
    comp.details = {
        "thickness_mm": int(t_fl * 1000),
        "p_kN_m2": round(p_fl, 2), "M_kNm_per_m": round(M_fl, 3),
        "Ast_mm2_per_m": round(Ast_fl, 1),
        "bar_dia": bar_fl["dia"], "bar_spacing_mm": bar_fl["spacing"],
    }
    result.add(comp); result.reinforcement["floor_slab"] = comp.details

    # ── Staging ────────────────────────────────────────────────────────────────
    W_tot = (GAMMA_W * actual_vol +
             GAMMA_RCC * (2 * (L + B) * H_total * t_lw + L * B * (t_fl + t_roof)))
    col_size = max(0.40, math.sqrt(W_tot / n_columns / (0.45 * fck * 1000)))
    col_size = round(col_size * 4) / 4
    result.reinforcement["staging"] = {
        "col_size_mm": int(col_size * 1000),
        "W_total_kN": round(W_tot, 1),
        "P_col_kN": round(W_tot / n_columns, 1),
    }

    # ── Volumes & Cost ─────────────────────────────────────────────────────────
    Vc_walls = 2 * ((L + B) * H_total * t_lw)
    Vc_floor = L * B * t_fl
    Vc_roof  = L * B * t_roof
    Vc_cols  = n_columns * col_size ** 2 * staging_height_m
    Vc_total = Vc_walls + Vc_floor + Vc_roof + Vc_cols
    W_stl    = Vc_total * 0.011 * 7850
    cost_tot = (Vc_total * 7500 + W_stl * 75) * 1.15
    result.volumes = {
        "concrete_walls_m3": round(Vc_walls, 2),
        "concrete_floor_m3": round(Vc_floor, 2),
        "concrete_roof_m3": round(Vc_roof, 2),
        "concrete_columns_m3": round(Vc_cols, 2),
        "total_concrete_m3": round(Vc_total, 2),
        "total_steel_kg": round(W_stl, 0),
    }
    result.cost_estimate = {
        "concrete_cost": round(Vc_total * 7500),
        "steel_cost": round(W_stl * 75),
        "total": round(cost_tot),
        "cost_per_m3_capacity": round(cost_tot / capacity_m3),
    }
    result.bbs = []   # simplified; full BBS in bbs.py
    return result
