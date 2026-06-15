"""
tests/test_design.py – pytest suite for elevated water tank design engines.
Run with: pytest tests/ -v
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from src.design.base import (
    choose_bar, neutral_axis, lever_arm, ast_from_moment,
    ast_from_tension, min_ast, CONCRETE, STEEL
)
from src.design.circular_tank    import design_circular_tank
from src.design.intze_tank        import design_intze_tank
from src.design.rectangular_tank  import design_rectangular_tank
from src.design.seismic           import seismic_forces, wind_forces, _Sa_g
from src.design.optimizer         import rank_tank_types
from src.design.is3370_tables     import get_ct_cm, get_rect_coeffs


# ─────────────────────────────────────────────────────────────────────────────
# Base utilities
# ─────────────────────────────────────────────────────────────────────────────
class TestBaseUtils:
    def test_neutral_axis_fe415_m25(self):
        k = neutral_axis(m=10.98, sigma_cbc=8.5, sigma_st=190)
        assert 0.3 < k < 0.5, f"k={k} out of expected range"

    def test_lever_arm(self):
        assert abs(lever_arm(0.4) - (1 - 0.4/3)) < 1e-9

    def test_choose_bar_returns_adequate(self):
        bar = choose_bar(Ast_reqd=600, spacing_mm=150)
        assert bar["Ast_prov"] >= 600
        assert bar["dia"] in [8,10,12,16,20,25,32,36]

    def test_ast_from_moment(self):
        c = CONCRETE["M25"]; s = STEEL["Fe415"]
        Ast = ast_from_moment(M_kNm_per_m=50, d_mm=250,
                              sigma_st=s["sigma_st_b"],
                              m=c["m"], sigma_cbc=c["sigma_cbc"])
        assert Ast > 0

    def test_ast_from_tension(self):
        Ast = ast_from_tension(T_kN_per_m=100, sigma_st_direct=150)
        assert abs(Ast - 100*1000/150) < 0.01

    def test_min_ast_fe415(self):
        ast = min_ast(thickness_mm=200, steel_grade="Fe415")
        assert abs(ast - 0.24/100 * 200 * 1000) < 0.01

    @pytest.mark.parametrize("grade", ["M20","M25","M30","M35"])
    def test_concrete_grade_m_values(self, grade):
        m = CONCRETE[grade]["m"]
        expected = 280 / (3 * CONCRETE[grade]["sigma_cbc"])
        assert abs(m - expected) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# IS 3370 Tables
# ─────────────────────────────────────────────────────────────────────────────
class TestIS3370Tables:
    def test_ct_cm_lengths(self):
        ct, cm, param = get_ct_cm(H=4.0, D=8.0, t=0.22)
        assert len(ct) == 11
        assert len(cm) == 11

    def test_ct_boundary_zero(self):
        ct, cm, _ = get_ct_cm(H=4.0, D=8.0, t=0.22)
        assert ct[0] == pytest.approx(0.0, abs=1e-3)   # top: free
        assert ct[-1] == pytest.approx(0.0, abs=1e-3)  # base: fixed (hoop=0)

    def test_ct_max_is_positive(self):
        ct, _, _ = get_ct_cm(H=4.0, D=8.0, t=0.22)
        assert max(ct) > 0

    def test_cm_base_negative(self):
        _, cm, _ = get_ct_cm(H=4.0, D=8.0, t=0.22)
        assert cm[-1] < 0  # tension on water face at fixed base

    def test_param_clamped(self):
        _, _, p = get_ct_cm(H=1.0, D=100.0, t=0.20)
        assert p >= 0.4

    def test_rect_coefficients_range(self):
        ax, ay_b, ay_m = get_rect_coeffs(L=5.0, H=3.0)
        assert 0 <= ax  <= 0.10
        assert 0 <= ay_b <= 0.12
        assert 0 <= ay_m <= 0.05


# ─────────────────────────────────────────────────────────────────────────────
# Circular Tank
# ─────────────────────────────────────────────────────────────────────────────
class TestCircularTank:
    @pytest.fixture
    def tank(self):
        return design_circular_tank(capacity_m3=500, concrete_grade="M25",
                                    steel_grade="Fe415")

    def test_volume_adequate(self, tank):
        assert tank.geometry["actual_vol_m3"] >= 500 * 0.99

    def test_has_components(self, tank):
        names = [c.name for c in tank.components]
        assert "Cylindrical Wall" in names
        assert "Top Dome (Roof)"  in names
        assert "Flat Floor Slab"  in names

    def test_wall_thickness_minimum(self, tank):
        t = tank.reinforcement["wall"]["thickness_mm"]
        assert t >= 200

    def test_hoop_steel_positive(self, tank):
        Ast = tank.reinforcement["wall"]["Ast_hoop_mm2_per_m"]
        assert Ast > 0

    def test_cost_positive(self, tank):
        assert tank.cost_estimate["total"] > 0

    def test_volumes_positive(self, tank):
        for k, v in tank.volumes.items():
            assert float(v) >= 0, f"{k}={v} is negative"

    @pytest.mark.parametrize("cap", [100, 500, 1000, 2000])
    def test_various_capacities(self, cap):
        r = design_circular_tank(capacity_m3=cap)
        assert r.geometry["actual_vol_m3"] >= cap * 0.99


# ─────────────────────────────────────────────────────────────────────────────
# Intze Tank
# ─────────────────────────────────────────────────────────────────────────────
class TestIntzeTank:
    @pytest.fixture
    def tank(self):
        return design_intze_tank(capacity_m3=1000, concrete_grade="M25",
                                 steel_grade="Fe415", cone_angle_deg=45)

    def test_volume_adequate(self, tank):
        assert tank.geometry["actual_vol_m3"] >= 1000 * 0.99

    def test_has_intze_components(self, tank):
        names = [c.name for c in tank.components]
        for expected in ["Top Dome", "Cylindrical Wall", "Conical Dome",
                         "Bottom Spherical Dome", "Bottom Ring Girder"]:
            assert any(expected in n for n in names), f"Missing: {expected}"

    def test_ring_girder_has_torsion(self, tank):
        T = tank.reinforcement["ring_girder"]["T_torsion_kNm"]
        assert T > 0

    def test_intze_check_present(self, tank):
        assert "intze_check" in tank.reinforcement

    def test_geometry_keys(self, tank):
        for key in ["D_int_m", "H_cylinder_m", "H_cone_m", "R_bot_dome_m"]:
            assert key in tank.geometry

    def test_cost_per_m3(self, tank):
        cpp = tank.cost_estimate["cost_per_m3_capacity"]
        assert 1000 < cpp < 50000   # sanity range ₹/m³

    @pytest.mark.parametrize("angle", [30, 45, 60])
    def test_cone_angles(self, angle):
        r = design_intze_tank(capacity_m3=500, cone_angle_deg=angle)
        assert r.geometry["actual_vol_m3"] >= 500 * 0.98


# ─────────────────────────────────────────────────────────────────────────────
# Rectangular Tank
# ─────────────────────────────────────────────────────────────────────────────
class TestRectangularTank:
    @pytest.fixture
    def tank(self):
        return design_rectangular_tank(capacity_m3=100, concrete_grade="M25",
                                       steel_grade="Fe415")

    def test_volume_adequate(self, tank):
        assert tank.geometry["actual_vol_m3"] >= 100 * 0.99

    def test_has_long_short_walls(self, tank):
        names = [c.name for c in tank.components]
        assert "Long Wall"  in names
        assert "Short Wall" in names

    def test_geometry_LB(self, tank):
        assert tank.geometry["L_m"] > tank.geometry["B_m"]

    def test_wall_steel_positive(self, tank):
        Ast = tank.reinforcement["long_wall"]["Ast_horiz_mm2_per_m"]
        assert Ast > 0


# ─────────────────────────────────────────────────────────────────────────────
# Seismic
# ─────────────────────────────────────────────────────────────────────────────
class TestSeismic:
    @pytest.fixture
    def circ_result(self):
        return design_circular_tank(capacity_m3=500)

    def test_base_shear_positive(self, circ_result):
        res = seismic_forces(
            tank_type="Circular", capacity_m3=500,
            geometry=circ_result.geometry,
            W_empty_tank_kN=1000, staging_height_m=12,
            zone="III", importance_factor=1.5,
        )
        assert res["V_B_kN"] > 0

    def test_ot_moment_positive(self, circ_result):
        res = seismic_forces(
            tank_type="Circular", capacity_m3=500,
            geometry=circ_result.geometry,
            W_empty_tank_kN=1000, staging_height_m=12,
        )
        assert res["M_ot_kNm"] > 0

    @pytest.mark.parametrize("zone,Z", [("II",0.10),("III",0.16),("IV",0.24),("V",0.36)])
    def test_zone_factors(self, circ_result, zone, Z):
        res = seismic_forces("Circular", 500, circ_result.geometry,
                             1000, 12, zone=zone)
        assert abs(res["Z"] - Z) < 1e-9

    def test_sa_g_soil_types(self):
        for soil in ["I", "II", "III"]:
            sa = _Sa_g(0.5, soil)
            assert 0 < sa <= 2.5

    def test_wind_base_shear(self, circ_result):
        res = wind_forces(geometry=circ_result.geometry,
                          basic_wind_speed_m_s=44)
        assert res["V_wind_kN"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# Optimiser
# ─────────────────────────────────────────────────────────────────────────────
class TestOptimizer:
    @pytest.mark.parametrize("cap,expected_types", [
        (50,  ["Circular", "Rectangular"]),
        (200, ["Circular", "Rectangular", "Intze"]),
        (500, ["Circular", "Intze"]),
        (2000,["Circular", "Intze"]),
    ])
    def test_ranked_includes_expected(self, cap, expected_types):
        ranked = rank_tank_types(capacity_m3=cap)
        names  = [nm for nm, _, _ in ranked]
        for t in expected_types:
            assert any(t in n for n in names), \
                f"Expected '{t}' in results for cap={cap}; got {names}"

    def test_best_has_lowest_composite_score(self):
        ranked  = rank_tank_types(capacity_m3=500)
        scores  = [sc["composite_score"] for _, _, sc in ranked]
        # First entry must have the minimum composite score
        assert scores[0] == min(scores)

    def test_all_have_positive_scores(self):
        ranked = rank_tank_types(capacity_m3=300)
        for _, _, sc in ranked:
            assert sc["composite_score"] > 0
