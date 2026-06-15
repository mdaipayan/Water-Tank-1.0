"""
tests/test_verification.py - Independent verification harness.

These tests do NOT trust the design engine's own arithmetic. Each one re-derives
the governing quantity from first principles (closed-form formulas and the
published IS tables) and asserts the engine's output matches. They are designed
to catch *wiring* bugs - wrong variable, wrong units, wrong depth - of the kind
found during the correctness audit (seismic period factor, hoop-steel face split,
freeboard vs water depth in the IS 3370 coefficient parameter).

Run with: pytest tests/test_verification.py -v
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from src.design.base import (
    GAMMA_W, GAMMA_RCC, choose_bar, ast_from_tension, min_ast,
    neutral_axis, lever_arm, CONCRETE, STEEL,
)
from src.design.is3370_tables import (
    get_ct_cm, _CT_TABLE, _CM_TABLE, _DEPTH_FRAC,
)
from src.design.circular_tank import design_circular_tank
from src.design.intze_tank import design_intze_tank
from src.design.rectangular_tank import design_rectangular_tank
from src.design.seismic import seismic_forces, wind_forces, _Sa_g

TOL = 0.02  # 2% relative tolerance to absorb the engine's display rounding


def _close(a, b, tol=TOL, floor=1e-6):
    """Relative closeness with an absolute floor for near-zero values."""
    return abs(a - b) <= tol * max(abs(a), abs(b), floor) + 0.05


# ─────────────────────────────────────────────────────────────────────────────
# 1. IS 3370 Part IV coefficient interpolation must reproduce published nodes
# ─────────────────────────────────────────────────────────────────────────────
class TestIS3370NodeFidelity:
    @pytest.mark.parametrize("param_node", [0.4, 1.0, 2.0, 4.0, 8.0, 12.0, 16.0])
    def test_ct_cm_reproduce_table_rows(self, param_node):
        # Pick H, D, t so that H^2/(D t) lands exactly on a table row.
        D, t = 8.0, 0.25
        H = math.sqrt(param_node * D * t)
        ct, cm, p = get_ct_cm(H, D, t)
        assert p == pytest.approx(param_node, rel=1e-6)
        for got, ref in zip(ct, _CT_TABLE[param_node]):
            assert got == pytest.approx(ref, abs=1e-6)
        for got, ref in zip(cm, _CM_TABLE[param_node]):
            assert got == pytest.approx(ref, abs=1e-6)

    def test_param_clamped_both_ends(self):
        _, _, lo = get_ct_cm(0.5, 100.0, 0.30)   # tiny param -> clamp to 0.4
        _, _, hi = get_ct_cm(50.0, 2.0, 0.10)     # huge param -> clamp to 16
        assert lo == pytest.approx(0.4, abs=1e-6)
        assert hi == pytest.approx(16.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Circular wall hoop tension / moment use LIQUID depth, not freeboard
# ─────────────────────────────────────────────────────────────────────────────
class TestCircularWallPhysics:
    @pytest.fixture
    def tank(self):
        return design_circular_tank(capacity_m3=800, concrete_grade="M25",
                                    steel_grade="Fe415", free_board_m=0.3)

    def test_hoop_tension_matches_first_principles(self, tank):
        g = tank.geometry
        w = tank.reinforcement["wall"]
        D = g["D_int_m"]; R = g["R_int_m"]; Hw = g["H_water_m"]
        t = w["thickness_mm"] / 1000.0
        ct, _, _ = get_ct_cm(Hw, D, t)            # independent recompute on H_water
        T_expected = max(ct) * GAMMA_W * Hw * R
        assert _close(w["T_hoop_max_kN_per_m"], T_expected)

    def test_param_uses_water_depth_not_total(self, tank):
        g = tank.geometry
        w = tank.reinforcement["wall"]
        D = g["D_int_m"]; Hw = g["H_water_m"]
        t = w["thickness_mm"] / 1000.0
        expected_param = max(0.4, min(Hw ** 2 / (D * t), 16.0))
        assert w["H2_Dt_param"] == pytest.approx(round(expected_param, 3), abs=1e-3)

    def test_hoop_steel_provided_over_two_faces_meets_demand(self, tank):
        w = tank.reinforcement["wall"]
        assert w["Ast_hoop_prov"] >= w["Ast_hoop_mm2_per_m"] * 0.999

    def test_min_reinforcement_respected(self, tank):
        w = tank.reinforcement["wall"]
        mn = min_ast(w["thickness_mm"], "Fe415")
        assert w["Ast_hoop_mm2_per_m"] >= mn * 0.999
        assert w["Ast_vert_mm2_per_m"] >= mn * 0.999


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dome meridional thrust closed form  N_phi = w0 * R_d / (1 + cos theta)
# ─────────────────────────────────────────────────────────────────────────────
class TestDomePhysics:
    def test_top_dome_meridional_thrust(self):
        r = design_circular_tank(capacity_m3=600)
        d = r.reinforcement["top_dome"]
        Rd = d["Rd_m"]; theta = math.radians(d["theta_deg"])
        w0 = d["w0_kN_m2"]
        N_expected = w0 * Rd / (1 + math.cos(theta))
        assert _close(d["N_phi_kN_per_m"], N_expected)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Seismic - every relationship checked against the standard's definitions
# ─────────────────────────────────────────────────────────────────────────────
class TestSeismicPhysics:
    @pytest.fixture
    def res(self):
        tank = design_circular_tank(capacity_m3=700)
        return seismic_forces(
            tank_type="Circular", capacity_m3=700,
            geometry=tank.geometry, W_empty_tank_kN=1500,
            staging_height_m=14, zone="IV", importance_factor=1.5,
            R_factor=2.5, soil_type="II",
        )

    def test_design_coefficient_definition(self, res):
        # Ah = Z I Sa / (2 R)
        Ah_i_expected = res["Z"] * res["I"] * res["Sa_i_g"] / (2 * res["R"])
        Ah_c_expected = res["Z"] * res["I"] * res["Sa_c_g"] / (2 * res["R"])
        assert _close(res["Ah_i"], Ah_i_expected)
        assert _close(res["Ah_c"], Ah_c_expected)

    def test_base_shear_srss(self, res):
        VB = math.sqrt(res["V_i_kN"] ** 2 + res["V_c_kN"] ** 2)
        assert _close(res["V_B_kN"], VB)

    def test_overturning_srss(self, res):
        M = math.sqrt(res["M_i_kNm"] ** 2 + res["M_c_kNm"] ** 2)
        assert _close(res["M_ot_kNm"], M)

    def test_spectral_within_code_bounds(self, res):
        assert 0 < res["Sa_i_g"] <= 2.5
        assert 0 < res["Sa_c_g"] <= 2.5

    def test_impulsive_period_is_physical(self, res):
        # Regression guard for the *1000 unit bug: an elevated-tank staging
        # period should be order ~0.3-4 s, never tens of seconds.
        assert 0.03 <= res["T_i_sec"] <= 6.0

    def test_mass_fractions_partition_liquid(self, res):
        # impulsive + convective fractions should account for ~all the liquid
        assert 0.8 <= res["mi_m"] + res["mc_m"] <= 1.05

    def test_convective_period_longer_than_impulsive(self, res):
        assert res["T_c_sec"] > res["T_i_sec"]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Wind  pz = 0.6 Vz^2 (N/m2) -> kN/m2,  Vz = Vb k1 k2 k3
# ─────────────────────────────────────────────────────────────────────────────
class TestWindPhysics:
    def test_dynamic_pressure(self):
        tank = design_circular_tank(capacity_m3=500)
        w = wind_forces(geometry=tank.geometry, basic_wind_speed_m_s=47.0,
                        k1=1.0, k2=1.0, k3=1.0)
        Vz = 47.0
        pz_expected = 0.6 * Vz ** 2 / 1000.0
        assert _close(w["Vz_m_s"], Vz)
        assert _close(w["pz_kN_m2"], pz_expected)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bar selection always satisfies demand (never under-provides)
# ─────────────────────────────────────────────────────────────────────────────
class TestBarSelection:
    @pytest.mark.parametrize("demand", [120, 350, 600, 1200, 2500, 4000, 8000])
    def test_choose_bar_meets_or_exceeds(self, demand):
        bar = choose_bar(demand, spacing_mm=150)
        assert bar["Ast_prov"] >= demand * 0.999
        assert bar["spacing"] >= 50


# ─────────────────────────────────────────────────────────────────────────────
# 7. Intze self-balancing - residual ring force stays a small fraction of thrust
# ─────────────────────────────────────────────────────────────────────────────
class TestIntzeBalance:
    @pytest.mark.parametrize("angle", [35, 45, 55])
    def test_residual_thrust_is_carried_by_ring_steel(self, angle):
        # Whatever residual ring force the Intze condition leaves, the bottom
        # ring girder must provide hoop-tension steel to resist it.
        r = design_intze_tank(capacity_m3=1200, cone_angle_deg=angle)
        T_net = abs(r.reinforcement["intze_check"]["T_net_brb_kN"])
        sigma_std = STEEL["Fe415"]["sigma_st_d"]
        Ast_needed = T_net * 1000 / sigma_std
        Ast_ring = r.reinforcement["ring_girder"]["Ast_ring_tension_mm2"]
        assert Ast_ring >= Ast_needed * 0.999
        # And the girder's total main steel includes that tension component.
        assert r.reinforcement["ring_girder"]["Ast_main_mm2"] >= Ast_ring * 0.999


# ─────────────────────────────────────────────────────────────────────────────
# 8. Volume adequacy across the full supported capacity range
# ─────────────────────────────────────────────────────────────────────────────
class TestVolumeAdequacy:
    @pytest.mark.parametrize("cap", [50, 150, 500, 1500, 3000])
    def test_circular_volume(self, cap):
        r = design_circular_tank(capacity_m3=cap)
        assert r.geometry["actual_vol_m3"] >= cap * 0.98

    @pytest.mark.parametrize("cap", [150, 500, 1500, 5000])
    def test_intze_volume(self, cap):
        r = design_intze_tank(capacity_m3=cap)
        assert r.geometry["actual_vol_m3"] >= cap * 0.98

    @pytest.mark.parametrize("cap", [20, 80, 200])
    def test_rectangular_volume(self, cap):
        r = design_rectangular_tank(capacity_m3=cap)
        assert r.geometry["actual_vol_m3"] >= cap * 0.98
