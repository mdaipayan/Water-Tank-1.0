"""
optimizer.py – Optimal tank type selector.
Designs all feasible tank types, ranks by cost/m³ capacity, and recommends best.
"""
from __future__ import annotations
from typing import List, Tuple
from .circular_tank import design_circular_tank
from .intze_tank import design_intze_tank
from .rectangular_tank import design_rectangular_tank
from .base import TankDesignResult


# Capacity thresholds (m³) for tank type feasibility
_TYPE_RANGES = {
    "Circular": (10, 5000),
    "Rectangular": (5, 300),
    "Intze": (100, 10000),
}


def rank_tank_types(
    capacity_m3: float,
    concrete_grade: str = "M25",
    steel_grade: str = "Fe415",
    staging_height_m: float = 12.0,
    n_columns: int = 6,
) -> List[Tuple[str, TankDesignResult, dict]]:
    """
    Design all feasible tank types for given capacity.
    Returns list of (rank_label, result, score_dict) sorted by cost efficiency.
    """
    results = []

    # Circular tank
    lo, hi = _TYPE_RANGES["Circular"]
    if lo <= capacity_m3 <= hi:
        try:
            r = design_circular_tank(
                capacity_m3=capacity_m3,
                concrete_grade=concrete_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_columns,
            )
            results.append(("Circular", r))
        except Exception as e:
            pass

    # Rectangular tank (small capacities)
    lo, hi = _TYPE_RANGES["Rectangular"]
    if lo <= capacity_m3 <= hi:
        try:
            n_col_rect = 4 if capacity_m3 <= 100 else n_columns
            r = design_rectangular_tank(
                capacity_m3=capacity_m3,
                concrete_grade=concrete_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_col_rect,
            )
            results.append(("Rectangular", r))
        except Exception as e:
            pass

    # Intze tank (large capacities)
    lo, hi = _TYPE_RANGES["Intze"]
    if lo <= capacity_m3 <= hi:
        try:
            r = design_intze_tank(
                capacity_m3=capacity_m3,
                concrete_grade=concrete_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_columns,
            )
            results.append(("Intze", r))
        except Exception as e:
            pass

    # Score and rank
    scored = []
    for name, res in results:
        score = _score(res, capacity_m3)
        scored.append((name, res, score))

    scored.sort(key=lambda x: x[2]["composite_score"])
    return scored


def _score(result: TankDesignResult, capacity_m3: float) -> dict:
    """Compute composite score (lower = better)."""
    cost_per_m3 = result.cost_estimate.get("cost_per_m3_capacity", 99999)
    concrete_m3 = result.volumes.get("total_concrete_m3", 999)
    n_warnings   = len(result.warnings)
    ok_penalty   = 0 if result.ok else 5000

    # Normalised cost score (primary)
    score_cost = cost_per_m3

    # Concrete intensity (secondary efficiency)
    score_intensity = concrete_m3 / capacity_m3 * 1000

    composite = score_cost + score_intensity * 0.1 + n_warnings * 200 + ok_penalty

    return {
        "cost_per_m3": cost_per_m3,
        "concrete_intensity": round(concrete_m3 / capacity_m3, 3),
        "n_warnings": n_warnings,
        "design_ok": result.ok,
        "composite_score": round(composite, 1),
        "recommendation": _recommendation(result, composite),
    }


def _recommendation(result: TankDesignResult, score: float) -> str:
    if not result.ok:
        return "❌ Design failed – needs revision"
    if score < 8000:
        return "✅ Excellent – economical & structurally sound"
    elif score < 12000:
        return "✅ Good – adequate design"
    elif score < 18000:
        return "⚠️ Acceptable – consider optimising geometry"
    else:
        return "⚠️ Costly – explore alternative tank type"


def auto_redesign_if_failed(
    result: TankDesignResult,
    capacity_m3: float,
    concrete_grade: str,
    steel_grade: str,
    staging_height_m: float,
) -> TankDesignResult:
    """
    If the primary design fails, attempt automatic parameter adjustments:
    - Upgrade concrete grade
    - Increase staging column count
    - Adjust H/D ratio
    Returns an improved (possibly still failing) design result with revised parameters noted.
    """
    if result.ok:
        return result

    revisions = []

    # Strategy 1: upgrade concrete
    grades = ["M20", "M25", "M30", "M35", "M40"]
    idx = grades.index(concrete_grade) if concrete_grade in grades else 1
    new_grade = grades[min(idx + 1, len(grades) - 1)]
    revisions.append(f"Upgraded concrete from {concrete_grade} → {new_grade}")

    # Strategy 2: more columns if staging failed
    stg_fail = any("staging" in w.lower() or "column" in w.lower() or "slender" in w.lower()
                   for w in result.warnings)
    n_col_new = 8 if stg_fail else 6

    tank_type = result.tank_type
    try:
        if "Intze" in tank_type:
            new_r = design_intze_tank(
                capacity_m3=capacity_m3,
                concrete_grade=new_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_col_new,
            )
        elif "Rectangular" in tank_type:
            new_r = design_rectangular_tank(
                capacity_m3=capacity_m3,
                concrete_grade=new_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_col_new,
            )
        else:
            new_r = design_circular_tank(
                capacity_m3=capacity_m3,
                concrete_grade=new_grade,
                steel_grade=steel_grade,
                staging_height_m=staging_height_m,
                n_columns=n_col_new,
            )
        new_r.warnings = [f"[Auto-Revised] {r}" for r in revisions] + new_r.warnings
        return new_r
    except Exception:
        result.warnings.append("[AutoRedesign] Automatic redesign also failed – manual check required.")
        return result
