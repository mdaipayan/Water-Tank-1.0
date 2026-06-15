"""
is3370_tables.py – Digitised coefficient tables from IS 3370 (Part IV):2009.

Table 9  – Hoop tension coefficients Ct  [T = Ct × γw H R]
Table 10 – Bending moment coefficients Cm [M = Cm × γw H³]
           Fixed base, Free top, Cylindrical walls

Tables 3–7: Rectangular tank wall moment coefficients
"""
from __future__ import annotations
import math
import numpy as np
from scipy.interpolate import RegularGridInterpolator

# ──────────────────────────────────────────────────────────────────────────────
# IS 3370 Part IV – Table 9: Hoop tension coefficients Ct
# Rows → H²/(Dt) parameter; Cols → depth fraction (0.0H … 1.0H from top)
# Fixed base, free top
# ──────────────────────────────────────────────────────────────────────────────
_CT_PARAMS = [0.4, 1.0, 2.0, 4.0, 8.0, 12.0, 16.0]
_DEPTH_FRAC = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

_CT_TABLE = {
    # H²/Dt :  [0.0H, 0.1H, 0.2H, 0.3H, 0.4H, 0.5H, 0.6H, 0.7H, 0.8H, 0.9H, 1.0H]
    0.4:  [0.000, 0.149, 0.134, 0.120, 0.101, 0.082, 0.060, 0.039, 0.019, 0.004, 0.000],
    1.0:  [0.000, 0.334, 0.301, 0.267, 0.229, 0.185, 0.134, 0.085, 0.041, 0.010, 0.000],
    2.0:  [0.000, 0.539, 0.485, 0.430, 0.371, 0.303, 0.222, 0.142, 0.068, 0.016, 0.000],
    4.0:  [0.000, 0.725, 0.659, 0.592, 0.516, 0.426, 0.320, 0.210, 0.104, 0.025, 0.000],
    8.0:  [0.000, 0.858, 0.781, 0.695, 0.607, 0.512, 0.398, 0.271, 0.143, 0.044, 0.000],
    12.0: [0.000, 0.906, 0.831, 0.730, 0.637, 0.536, 0.428, 0.302, 0.168, 0.059, 0.000],
    16.0: [0.000, 0.930, 0.851, 0.750, 0.655, 0.552, 0.447, 0.322, 0.184, 0.068, 0.000],
}

# IS 3370 Part IV – Table 10: Bending moment coefficients Cm
# M = Cm × γw × H³   (negative = tension on water face)
_CM_TABLE = {
    0.4:  [ 0.000,  0.001,  0.002,  0.003,  0.003,  0.002,  0.000, -0.003, -0.006, -0.008, -0.010],
    1.0:  [ 0.000,  0.002,  0.004,  0.005,  0.006,  0.005,  0.002, -0.003, -0.010, -0.018, -0.025],
    2.0:  [ 0.000,  0.002,  0.005,  0.008,  0.009,  0.008,  0.005, -0.001, -0.011, -0.024, -0.040],
    4.0:  [ 0.000,  0.001,  0.003,  0.006,  0.009,  0.010,  0.008,  0.003, -0.007, -0.026, -0.053],
    8.0:  [ 0.000,  0.000,  0.001,  0.003,  0.007,  0.010,  0.011,  0.009,  0.001, -0.021, -0.059],
    12.0: [ 0.000,  0.000,  0.001,  0.003,  0.007,  0.011,  0.013,  0.012,  0.004, -0.018, -0.059],
    16.0: [ 0.000,  0.000,  0.000,  0.002,  0.006,  0.010,  0.013,  0.014,  0.007, -0.015, -0.059],
}


def get_ct_cm(H: float, D: float, t: float):
    """
    Interpolate IS 3370 Part IV hoop (Ct) and BM (Cm) coefficients.
    Returns lists of length 11 at depth fractions 0.0..1.0H.
    """
    param = H ** 2 / (D * t)
    param = max(0.4, min(param, 16.0))

    params = np.array(_CT_PARAMS)
    depths = np.array(_DEPTH_FRAC)

    ct_matrix = np.array([_CT_TABLE[p] for p in _CT_PARAMS])
    cm_matrix = np.array([_CM_TABLE[p] for p in _CT_PARAMS])

    ct_interp = RegularGridInterpolator((params, depths), ct_matrix,
                                        method="linear", bounds_error=False,
                                        fill_value=None)
    cm_interp = RegularGridInterpolator((params, depths), cm_matrix,
                                        method="linear", bounds_error=False,
                                        fill_value=None)

    pts = np.array([[param, d] for d in depths])
    ct = ct_interp(pts).tolist()
    cm = cm_interp(pts).tolist()
    return ct, cm, round(param, 3)


# ──────────────────────────────────────────────────────────────────────────────
# IS 3370 Part IV – Tables 3–7: Rectangular wall moment coefficients
# Mx = αx × p0 × L²  (horizontal BM, tension on liquid face)
# My = αy × p0 × H²  (vertical BM)
# where p0 = γw H = max pressure at base
# Table 3: three edges fixed, one edge (top) free
# ──────────────────────────────────────────────────────────────────────────────
# Simplified representative values from Table 3 (IS 3370 Pt IV)
# Rows: L/H; Cols: horizontal (αx at mid-span, 0.5H), vertical (αy at base, 1.0H)
_RECT_LH  = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
# αx at mid-height, mid-span (max positive horizontal BM)
_RECT_AX  = [0.000, 0.005, 0.011, 0.018, 0.025, 0.031, 0.036, 0.043, 0.048]
# αy at base (max negative vertical BM)
_RECT_AY_BASE = [0.060, 0.052, 0.045, 0.038, 0.033, 0.028, 0.025, 0.020, 0.016]
# αy at mid-height (max positive vertical BM)
_RECT_AY_MID  = [0.015, 0.018, 0.020, 0.021, 0.021, 0.020, 0.019, 0.017, 0.014]


def get_rect_coeffs(L: float, H: float):
    """
    Interpolate rectangular wall BM coefficients for L/H ratio.
    Returns (αx_midspan, αy_base, αy_mid).
    """
    lh = max(0.5, min(L / H, 3.0))
    lh_arr = np.array(_RECT_LH)
    ax   = float(np.interp(lh, lh_arr, _RECT_AX))
    ay_b = float(np.interp(lh, lh_arr, _RECT_AY_BASE))
    ay_m = float(np.interp(lh, lh_arr, _RECT_AY_MID))
    return ax, ay_b, ay_m
