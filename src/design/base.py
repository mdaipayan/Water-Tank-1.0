"""
base.py – IS Code constants, permissible stresses, and shared design utilities.
References: IS 3370:2009 (Parts I & II), IS 456:2000, IS 875:1987, IS 1893:2016
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Concrete grades – IS 3370 Part II, Table 1
# ──────────────────────────────────────────────────────────────────────────────
CONCRETE = {
    "M20": {"fck": 20,  "sigma_cbc": 7.0,  "sigma_cc": 5.0},
    "M25": {"fck": 25,  "sigma_cbc": 8.5,  "sigma_cc": 6.0},
    "M30": {"fck": 30,  "sigma_cbc": 10.0, "sigma_cc": 8.0},
    "M35": {"fck": 35,  "sigma_cbc": 11.5, "sigma_cc": 9.0},
    "M40": {"fck": 40,  "sigma_cbc": 13.0, "sigma_cc": 10.0},
}

# Modular ratio  m = 280 / (3 * sigma_cbc)  [IS 456 cl. B-1.3]
for _g in CONCRETE.values():
    _g["m"] = round(280 / (3 * _g["sigma_cbc"]), 3)

# ──────────────────────────────────────────────────────────────────────────────
# Steel grades – IS 3370 Part II, Table 2
# ──────────────────────────────────────────────────────────────────────────────
STEEL = {
    "Fe250": {"fy": 250, "sigma_st_b": 125, "sigma_st_d": 115},
    "Fe415": {"fy": 415, "sigma_st_b": 190, "sigma_st_d": 150},
    "Fe500": {"fy": 500, "sigma_st_b": 190, "sigma_st_d": 175},
}

# ──────────────────────────────────────────────────────────────────────────────
# Unit weights
# ──────────────────────────────────────────────────────────────────────────────
GAMMA_W   = 9.81   # kN/m³  – water
GAMMA_RCC = 25.0   # kN/m³  – reinforced concrete (IS 875 Part 1)

# ──────────────────────────────────────────────────────────────────────────────
# Min concrete cover to reinforcement (IS 3370 Part I, cl 4.1)
# ──────────────────────────────────────────────────────────────────────────────
COVER_WATER_FACE = 45   # mm
COVER_OTHER_FACE = 25   # mm

# ──────────────────────────────────────────────────────────────────────────────
# Minimum reinforcement (IS 3370 Part II, cl. 7)  % of gross area
# ──────────────────────────────────────────────────────────────────────────────
MIN_REINF = {
    "Fe250": 0.30,   # plain bars
    "Fe415": 0.24,
    "Fe500": 0.24,
}

# ──────────────────────────────────────────────────────────────────────────────
# Seismic zone data  (IS 1893 Part 1 Table 2)
# ──────────────────────────────────────────────────────────────────────────────
SEISMIC_ZONE = {
    "II":  {"Z": 0.10, "label": "Zone II – Low"},
    "III": {"Z": 0.16, "label": "Zone III – Moderate"},
    "IV":  {"Z": 0.24, "label": "Zone IV – Severe"},
    "V":   {"Z": 0.36, "label": "Zone V – Very Severe"},
}

# ──────────────────────────────────────────────────────────────────────────────
# Wind basic speeds (IS 875 Part 3, Fig. 1)  m/s
# ──────────────────────────────────────────────────────────────────────────────
WIND_BASIC_SPEED = {
    "33": 33.0, "39": 39.0, "44": 44.0, "47": 47.0,
    "50": 50.0, "55": 55.0,
}

# ──────────────────────────────────────────────────────────────────────────────
# Bar data: diameter → area (mm²)
# ──────────────────────────────────────────────────────────────────────────────
BAR_AREA = {
    8:  50.27,  10:  78.54,  12: 113.10,  16: 201.06,
    20: 314.16, 25: 490.87,  32: 804.25,  36: 1017.88,
}
STANDARD_BARS = sorted(BAR_AREA.keys())


# ──────────────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────────────
def choose_bar(Ast_reqd: float, spacing_mm: float = 150) -> Dict:
    """
    Given required Ast (mm²/m), choose minimum bar diameter
    and actual spacing to satisfy Ast at given or reduced spacing.
    Returns dict with dia, spacing, Ast_prov.
    """
    for dia in STANDARD_BARS:
        area_bar = BAR_AREA[dia]
        sp = (area_bar / Ast_reqd) * 1000  # mm spacing for Ast_reqd mm²/m
        sp = min(sp, spacing_mm)           # cap at max spacing
        sp = max(sp, 50)                   # min spacing
        sp = round(sp / 5) * 5            # round to 5 mm
        Ast_prov = (area_bar / sp) * 1000
        if Ast_prov >= Ast_reqd:
            return {"dia": dia, "spacing": int(sp), "Ast_prov": round(Ast_prov, 1)}
    # Last resort: use 32 mm bars at close spacing
    dia = 32
    sp = max(round((BAR_AREA[dia] / Ast_reqd) * 1000 / 5) * 5, 75)
    return {"dia": dia, "spacing": int(sp),
            "Ast_prov": round((BAR_AREA[dia] / sp) * 1000, 1)}


def neutral_axis(m: float, sigma_cbc: float, sigma_st: float) -> float:
    """Critical neutral axis depth factor k = m·σcbc / (m·σcbc + σst)."""
    return (m * sigma_cbc) / (m * sigma_cbc + sigma_st)


def lever_arm(k: float) -> float:
    """Lever arm factor j = 1 - k/3."""
    return 1 - k / 3


def min_ast(thickness_mm: float, steel_grade: str) -> float:
    """Minimum Ast (mm²/m) per face per IS 3370 Part II cl. 7."""
    return MIN_REINF[steel_grade] / 100 * thickness_mm * 1000


def required_thickness(M_kNm_per_m: float, sigma_cbc: float,
                        sigma_st: float, m: float,
                        cover_mm: float = 45) -> float:
    """
    Minimum wall/slab thickness (mm) for given BM using WSM.
    d_req = sqrt(M * 10^6 / (0.5 * k * j * sigma_cbc * b))  with b=1000mm
    Returns total thickness = d + cover.
    """
    k = neutral_axis(m, sigma_cbc, sigma_st)
    j = lever_arm(k)
    Q = 0.5 * sigma_cbc * k * j   # MR coefficient
    d_req = math.sqrt(abs(M_kNm_per_m) * 1e6 / (Q * 1000)) if M_kNm_per_m else 0
    return max(d_req + cover_mm, 150)


def ast_from_moment(M_kNm_per_m: float, d_mm: float,
                    sigma_st: float, m: float, sigma_cbc: float) -> float:
    """Ast (mm²/m) from bending moment using WSM."""
    if M_kNm_per_m <= 0:
        return 0.0
    k = neutral_axis(m, sigma_cbc, sigma_st)
    j = lever_arm(k)
    return (M_kNm_per_m * 1e6) / (sigma_st * j * d_mm)


def ast_from_tension(T_kN_per_m: float, sigma_st_direct: float) -> float:
    """Ast (mm²/m) from direct tension."""
    return (T_kN_per_m * 1000) / sigma_st_direct


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass shared across all tank types
# ──────────────────────────────────────────────────────────────────────────────
def fnum(x, p: int = 2) -> str:
    """Format a number for inclusion in a LaTeX expression (no thousands sep)."""
    try:
        if float(x) == int(x):
            return f"{int(x)}"
        return f"{x:.{p}f}"
    except (TypeError, ValueError):
        return str(x)


@dataclass
class ComponentResult:
    name: str
    ok: bool = True
    warnings: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)
    formulas: List[Dict] = field(default_factory=list)   # worked LaTeX steps

    def fail(self, msg: str):
        self.ok = False
        self.warnings.append(msg)

    def warn(self, msg: str):
        self.warnings.append(msg)

    def step(self, label: str, latex: str, ref: str = ""):
        """Record one worked calculation step as LaTeX (symbol = expr = subst = result)."""
        self.formulas.append({"label": label, "latex": latex, "ref": ref})


@dataclass
class TankDesignResult:
    tank_type: str
    capacity_m3: float
    ok: bool = True
    components: List[ComponentResult] = field(default_factory=list)
    geometry: Dict = field(default_factory=dict)
    reinforcement: Dict = field(default_factory=dict)
    volumes: Dict = field(default_factory=dict)   # concrete, steel volumes
    cost_estimate: Dict = field(default_factory=dict)
    bbs: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add(self, comp: ComponentResult):
        self.components.append(comp)
        if not comp.ok:
            self.ok = False
            self.warnings.extend(comp.warnings)

    @property
    def total_cost(self) -> float:
        return self.cost_estimate.get("total", 0.0)
