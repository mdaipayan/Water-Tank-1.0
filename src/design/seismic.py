"""
seismic.py – IS 1893 Part 2:2016 two-mass model seismic design for elevated tanks.
"""
from __future__ import annotations
import math
from .base import SEISMIC_ZONE, GAMMA_W


def seismic_forces(
    tank_type: str,
    capacity_m3: float,
    geometry: dict,
    W_empty_tank_kN: float,
    staging_height_m: float,
    zone: str = "III",
    importance_factor: float = 1.5,
    R_factor: float = 2.5,
    soil_type: str = "II",
) -> dict:
    """
    Compute seismic base shear per IS 1893 Part 2:2016 (two-mass model).

    Parameters
    ----------
    geometry  : dict from design result (must contain D_int_m or L_m/B_m)
    Returns dict with impulsive/convective forces, base shear, OTM.
    """
    Z = SEISMIC_ZONE.get(zone, SEISMIC_ZONE["III"])["Z"]
    I = importance_factor
    R = R_factor

    m_l = GAMMA_W * capacity_m3 / 9.81   # liquid mass (tonnes)

    # Determine tank dimensions
    if "D_int_m" in geometry:
        D = geometry["D_int_m"]
        h = geometry.get("H_water_m", geometry.get("H_cylinder_m", 3.0))
        h_D = h / D
        # IS 1893 Part 2 Table 1 – mass ratios for circular tank
        # mi/m and mc/m as function of h/D
        mi_m  = _interp_mi_m_circ(h_D)
        mc_m  = _interp_mc_m_circ(h_D)
        hi_h  = _interp_hi_h_circ(h_D)    # height of impulsive mass (from base of liquid)
        hc_h  = _interp_hc_h_circ(h_D)
        L_char = D
    else:
        L = geometry["L_m"]; B = geometry["B_m"]
        h = geometry.get("H_water_m", 3.0)
        h_L = h / L
        mi_m = _interp_mi_m_rect(h_L)
        mc_m = _interp_mc_m_rect(h_L)
        hi_h = 0.375; hc_h = 0.613
        L_char = L

    mi = mi_m * m_l   # impulsive liquid mass (t)
    mc = mc_m * m_l   # convective liquid mass (t)
    ms = W_empty_tank_kN / 9.81  # structural mass (t)

    # Heights from base of staging
    h_i = hi_h * h + staging_height_m
    h_c = hc_h * h + staging_height_m

    # ── Impulsive time period (staging lateral stiffness) ─────────────────────
    # Simplified: approximate lateral stiffness K_s
    n_c = geometry.get("n_columns", 6)
    D_col = 0.50   # assumed 500 mm columns
    E_c = 5000 * math.sqrt(25) * 1e3   # kN/m² for M25
    I_col = math.pi / 64 * D_col ** 4
    K_s = n_c * 12 * E_c * I_col / staging_height_m ** 3   # kN/m

    m_i_total = (mi + ms) * 1000   # kg → convert for period calc in tonnes? use kN·s²/m
    m_i_total_t = (mi + ms)        # tonnes
    T_i = 2 * math.pi * math.sqrt(m_i_total_t / K_s * 1000)  # sec (approx)
    T_i = max(T_i, 0.03)

    # ── Convective time period ─────────────────────────────────────────────────
    T_c = 2 * math.pi / math.sqrt(3.68 * 9.81 / L_char * math.tanh(3.68 * h / L_char))

    # ── Spectral accelerations ─────────────────────────────────────────────────
    Sa_i_g = _Sa_g(T_i, soil_type)
    Sa_c_g = _Sa_g(T_c, soil_type)

    # Design horizontal seismic coefficients
    Ah_i = Z * I * Sa_i_g / (2 * R)
    Ah_c = Z * I * Sa_c_g / (2 * R)

    # ── Base shear ─────────────────────────────────────────────────────────────
    g = 9.81
    V_i = Ah_i * (mi + ms) * g    # kN
    V_c = Ah_c * mc * g           # kN
    V_B = math.sqrt(V_i ** 2 + V_c ** 2)

    # ── Overturning moment at base of staging ──────────────────────────────────
    M_i = V_i * h_i
    M_c = V_c * h_c
    M_ot = math.sqrt(M_i ** 2 + M_c ** 2)

    return {
        "zone": zone, "Z": Z, "I": I, "R": R,
        "h_D_ratio": round(h / L_char, 3),
        "mi_m": round(mi_m, 3), "mc_m": round(mc_m, 3),
        "mi_t": round(mi, 2), "mc_t": round(mc, 2), "ms_t": round(ms, 2),
        "T_i_sec": round(T_i, 3), "T_c_sec": round(T_c, 3),
        "Sa_i_g": round(Sa_i_g, 4), "Sa_c_g": round(Sa_c_g, 4),
        "Ah_i": round(Ah_i, 4), "Ah_c": round(Ah_c, 4),
        "V_i_kN": round(V_i, 1), "V_c_kN": round(V_c, 1),
        "V_B_kN": round(V_B, 1),
        "M_i_kNm": round(M_i, 1), "M_c_kNm": round(M_c, 1),
        "M_ot_kNm": round(M_ot, 1),
        "lateral_stiffness_kN_per_m": round(K_s, 1),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Interpolation tables – IS 1893 Part 2:2016 (Table 1 & Table 2)
# ──────────────────────────────────────────────────────────────────────────────
import numpy as np

_H_D_CIRC = [0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]
_MI_M_CIRC = [0.176, 0.300, 0.442, 0.548, 0.686, 0.763, 0.810, 0.842]
_MC_M_CIRC = [0.824, 0.700, 0.558, 0.452, 0.314, 0.237, 0.190, 0.158]
_HI_H_CIRC = [0.400, 0.375, 0.338, 0.306, 0.269, 0.250, 0.239, 0.231]
_HC_H_CIRC = [0.521, 0.583, 0.639, 0.664, 0.679, 0.668, 0.655, 0.640]

_H_L_RECT  = [0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]
_MI_M_RECT = [0.157, 0.272, 0.414, 0.528, 0.681, 0.763, 0.810, 0.842]
_MC_M_RECT = [0.843, 0.728, 0.586, 0.472, 0.319, 0.237, 0.190, 0.158]


def _interp_mi_m_circ(h_D): return float(np.interp(h_D, _H_D_CIRC, _MI_M_CIRC))
def _interp_mc_m_circ(h_D): return float(np.interp(h_D, _H_D_CIRC, _MC_M_CIRC))
def _interp_hi_h_circ(h_D): return float(np.interp(h_D, _H_D_CIRC, _HI_H_CIRC))
def _interp_hc_h_circ(h_D): return float(np.interp(h_D, _H_D_CIRC, _HC_H_CIRC))
def _interp_mi_m_rect(h_L): return float(np.interp(h_L, _H_L_RECT, _MI_M_RECT))
def _interp_mc_m_rect(h_L): return float(np.interp(h_L, _H_L_RECT, _MC_M_RECT))


def _Sa_g(T: float, soil_type: str) -> float:
    """
    IS 1893 Part 1:2016, Cl 6.4.2 – Design spectral acceleration Sa/g.
    soil_type: 'I'=Rock, 'II'=Medium soil, 'III'=Soft soil
    """
    if soil_type == "I":      # Hard rock / Rock
        if T <= 0.10: return 1 + 15 * T
        elif T <= 0.40: return 2.50
        elif T <= 4.00: return 1.00 / T
        else: return 0.25
    elif soil_type == "II":   # Medium soil
        if T <= 0.10: return 1 + 15 * T
        elif T <= 0.55: return 2.50
        elif T <= 4.00: return 1.36 / T
        else: return 0.34
    else:                     # Soft soil
        if T <= 0.10: return 1 + 15 * T
        elif T <= 0.67: return 2.50
        elif T <= 4.00: return 1.67 / T
        else: return 0.42


def wind_forces(
    geometry: dict,
    basic_wind_speed_m_s: float = 44.0,
    staging_height_m: float = 12.0,
    k1: float = 1.0, k2: float = 1.0, k3: float = 1.0,
    Cf: float = 0.7,
) -> dict:
    """
    Wind force on elevated tank per IS 875 Part 3.
    Returns base shear and OTM due to wind.
    """
    Vz = basic_wind_speed_m_s * k1 * k2 * k3
    pz = 0.6 * Vz ** 2 / 1000   # kN/m²   (IS 875 Pt3 cl. 7.2)

    D_tank = geometry.get("D_int_m", geometry.get("L_m", 5.0))
    H_tank_total = (geometry.get("H_total_m", geometry.get("H_cylinder_m", 3.0))
                    + geometry.get("H_cone_m", 0))

    # Projected area of tank
    A_tank = D_tank * H_tank_total

    # Force on staging (simplified – use 60% of projected area)
    D_col  = 0.50
    n_col  = geometry.get("n_columns", 6)
    A_stag = D_col * staging_height_m * n_col * 0.6

    F_tank = Cf * A_tank * pz
    F_stag = Cf * A_stag * pz

    h_cg_tank  = staging_height_m + H_tank_total / 2
    h_cg_stag  = staging_height_m / 2

    V_wind  = F_tank + F_stag
    M_wind  = F_tank * h_cg_tank + F_stag * h_cg_stag

    return {
        "Vz_m_s": round(Vz, 1), "pz_kN_m2": round(pz, 4),
        "F_tank_kN": round(F_tank, 2), "F_staging_kN": round(F_stag, 2),
        "V_wind_kN": round(V_wind, 2), "M_wind_kNm": round(M_wind, 2),
    }
