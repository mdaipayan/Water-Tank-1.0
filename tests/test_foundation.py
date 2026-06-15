"""
tests/test_foundation.py - Independent verification of the foundation module.
Each check re-derives the governing quantity from first principles.
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest

from src.design.foundation import (
    design_foundation, development_length, foundation_from_result,
    _column_ring_radius, MU_FRICTION,
)
from src.design.circular_tank import design_circular_tank
from src.design.intze_tank import design_intze_tank
from src.design.seismic import seismic_forces, wind_forces


def _base(**kw):
    args = dict(P_col_service_kN=800, n_columns=6, R_col_m=4.0, col_size_m=0.5,
                M_ot_kNm=1200, V_lat_kN=180, W_total_kN=6000, sbc_kN_m2=150)
    args.update(kw)
    return design_foundation(**args)


class TestDevelopmentLength:
    def test_formula_hysd_m25(self):
        # Ld = phi*sigma/(4*tau_bd), tau_bd(M25)=1.4*1.6 for deformed bars
        Ld = development_length(16, 25, 190.0, deformed=True)
        expected = 16 * 190.0 / (4 * 1.4 * 1.6)
        assert Ld == pytest.approx(expected, rel=1e-9)

    def test_plain_bar_shorter_than_deformed_isnt(self):
        # deformed bars have HIGHER bond -> SHORTER Ld than the plain-bar baseline
        assert development_length(16, 25, 190, True) < development_length(16, 25, 190, False)


class TestFootingMechanics:
    def test_overturning_axial_increment(self):
        r = _base()
        d = r.details
        expected_dP = 2 * 1200 / (6 * 4.0)
        assert d["dP_overturning_kN"] == pytest.approx(expected_dP, rel=1e-3)
        assert d["P_max_kN"] == pytest.approx(800 + expected_dP, rel=1e-3)

    def test_bearing_within_allowable(self):
        d = _base().details
        # lateral present -> 25% overstress allowed
        assert d["bearing_pressure_kN_m2"] <= d["sbc_allow_kN_m2"] * 1.01
        assert d["sbc_allow_kN_m2"] == pytest.approx(150 * 1.25, rel=1e-6)

    def test_footing_area_carries_load(self):
        d = _base().details
        q = d["bearing_pressure_kN_m2"]; B = d["footing_size_m"]
        assert q * B * B == pytest.approx(d["P_max_kN"] * 1.10, rel=0.03)

    def test_punching_depth_satisfies_allowable(self):
        # Recompute punching stress at the designed depth; must be within allowable.
        d = _base().details
        a, B = 0.5, d["footing_size_m"]
        dd = d["eff_depth_mm"] / 1000.0
        q_net = d["P_max_kN"] / (B * B)
        crit = a + dd
        Vp = q_net * (B * B - crit * crit)
        tau = (Vp * 1e3) / (4 * crit * 1e3 * dd * 1e3)
        assert tau <= d["punching_tau_perm_N_mm2"] * 1.05

    def test_min_steel_respected(self):
        d = _base().details
        Ast_min = 0.12 / 100 * d["footing_thickness_mm"] * 1000
        assert d["Ast_mm2_per_m"] >= Ast_min * 0.999
        assert d["Ast_prov_mm2_per_m"] >= d["Ast_mm2_per_m"] * 0.999


class TestStability:
    def test_overturning_fos_definition(self):
        d = _base(M_ot_kNm=1500, W_total_kN=7000, R_col_m=4.0).details
        assert d["FoS_overturning"] == pytest.approx(7000 * 4.0 / 1500, rel=1e-3)

    def test_sliding_fos_definition(self):
        d = _base(V_lat_kN=200, W_total_kN=7000).details
        assert d["FoS_sliding"] == pytest.approx(MU_FRICTION * 7000 / 200, rel=1e-3)

    def test_low_overturning_fos_flags_failure(self):
        # huge moment, light tank -> must fail overturning
        r = _base(M_ot_kNm=40000, W_total_kN=3000, R_col_m=4.0)
        assert r.ok is False
        assert any("Overturning" in w for w in r.warnings)

    def test_uplift_flagged(self):
        # dP > P_col -> windward uplift
        r = _base(P_col_service_kN=300, M_ot_kNm=20000, n_columns=6, R_col_m=4.0)
        assert r.details["uplift"] is True


class TestColumnRingRadius:
    def test_circular_uses_internal_radius(self):
        geo = {"R_int_m": 5.0, "D_int_m": 10.0}
        assert _column_ring_radius("Circular", geo) == pytest.approx(5.0)

    def test_rectangular_uses_diagonal(self):
        geo = {"L_m": 6.0, "B_m": 4.0}
        expected = 0.8 * math.hypot(3.0, 2.0)
        assert _column_ring_radius("Rectangular Tank", geo) == pytest.approx(expected)


class TestIntegration:
    def test_runs_on_circular_design(self):
        tank = design_circular_tank(capacity_m3=600)
        seis = seismic_forces("Circular", 600, tank.geometry, 1200, 12, zone="IV")
        wind = wind_forces(geometry=tank.geometry, basic_wind_speed_m_s=44)
        comp = foundation_from_result(tank, seis, wind, sbc_kN_m2=150)
        d = comp.details
        assert d["footing_size_m"] >= 1.0
        assert d["footing_thickness_mm"] >= 150
        assert d["Ast_prov_mm2_per_m"] > 0

    def test_runs_on_intze_design(self):
        tank = design_intze_tank(capacity_m3=1500)
        seis = seismic_forces("Intze", 1500, tank.geometry, 3000, 16, zone="III")
        comp = foundation_from_result(tank, seis, None, sbc_kN_m2=200)
        assert comp.details["footing_size_m"] >= 1.0
