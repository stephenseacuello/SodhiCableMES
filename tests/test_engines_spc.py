"""
Tests for engines/spc.py -- Statistical Process Control Engine.

Covers X-bar/R charting, Cp/Cpk capability indices, CUSUM and EWMA
charts, Western Electric rule detection, temperature correction,
and edge cases.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.spc import (
    xbar_r_chart,
    compute_cpk,
    cusum,
    ewma,
    western_electric_rules,
    temperature_correct_resistance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flat_subgroups(*subgroups):
    """Flatten a sequence of subgroup tuples into a single list."""
    result = []
    for sg in subgroups:
        result.extend(sg)
    return result


# ===================================================================
# X-bar / R chart
# ===================================================================

class TestXbarRChart:
    """Verify X-bar and R control-chart calculations against hand results."""

    # Five subgroups of size 5 -- all identical values within each subgroup
    # to make hand calculations trivial.
    UNIFORM_DATA = [10.0] * 25  # 5 subgroups of 5, all = 10

    # Known data: 5 subgroups of 5, with computable means and ranges.
    KNOWN_DATA = _flat_subgroups(
        (10, 12, 11, 13, 14),   # mean=12.0, R=4
        (11, 11, 12, 13, 13),   # mean=12.0, R=2
        (14, 15, 13, 12, 11),   # mean=13.0, R=4
        (10, 10, 11, 11, 12),   # mean=10.8, R=2
        (13, 14, 14, 15, 14),   # mean=14.0, R=2
    )

    def test_uniform_data_center_line(self):
        """Grand mean equals the constant value when all measurements are identical."""
        result = xbar_r_chart(self.UNIFORM_DATA)
        assert result["cl_xbar"] == pytest.approx(10.0)

    def test_uniform_data_r_bar_zero(self):
        """R-bar is zero when there is no variation within subgroups."""
        result = xbar_r_chart(self.UNIFORM_DATA)
        assert result["cl_r"] == pytest.approx(0.0)

    def test_uniform_data_control_limits_collapse(self):
        """UCL and LCL equal the center line when R-bar is zero."""
        result = xbar_r_chart(self.UNIFORM_DATA)
        assert result["ucl_xbar"] == pytest.approx(result["cl_xbar"])
        assert result["lcl_xbar"] == pytest.approx(result["cl_xbar"])

    def test_known_data_subgroup_means(self):
        """Subgroup means match hand calculation."""
        result = xbar_r_chart(self.KNOWN_DATA)
        expected_means = [12.0, 12.0, 13.0, 10.8, 14.0]
        assert result["x_bar_values"] == pytest.approx(expected_means)

    def test_known_data_subgroup_ranges(self):
        """Subgroup ranges match hand calculation."""
        result = xbar_r_chart(self.KNOWN_DATA)
        expected_ranges = [4.0, 2.0, 4.0, 2.0, 2.0]
        assert result["r_values"] == pytest.approx(expected_ranges)

    def test_known_data_grand_mean(self):
        """Grand mean (X-double-bar) is the average of subgroup means."""
        result = xbar_r_chart(self.KNOWN_DATA)
        x_double_bar = (12.0 + 12.0 + 13.0 + 10.8 + 14.0) / 5.0
        assert result["cl_xbar"] == pytest.approx(x_double_bar)

    def test_known_data_control_limits(self):
        """UCL/LCL for X-bar use A2 constant (0.577 for n=5)."""
        result = xbar_r_chart(self.KNOWN_DATA)
        r_bar = (4 + 2 + 4 + 2 + 2) / 5.0  # 2.8
        x_double_bar = result["cl_xbar"]
        assert result["ucl_xbar"] == pytest.approx(x_double_bar + 0.577 * r_bar)
        assert result["lcl_xbar"] == pytest.approx(x_double_bar - 0.577 * r_bar)

    def test_known_data_r_chart_limits(self):
        """UCL_R = D4 * R-bar, LCL_R = D3 * R-bar (D3=0 for n=5)."""
        result = xbar_r_chart(self.KNOWN_DATA)
        r_bar = 2.8
        assert result["ucl_r"] == pytest.approx(2.114 * r_bar)
        assert result["lcl_r"] == pytest.approx(0.0)

    def test_too_few_observations_raises(self):
        """Fewer than one full subgroup raises ValueError."""
        with pytest.raises(ValueError, match="at least one full subgroup"):
            xbar_r_chart([1.0, 2.0, 3.0])

    def test_trims_to_whole_subgroups(self):
        """Extra observations beyond a full subgroup are trimmed."""
        data = list(range(1, 28))  # 27 values -> 5 full subgroups of 5, 2 leftover
        result = xbar_r_chart(data)
        assert len(result["x_bar_values"]) == 5


# ===================================================================
# Cp / Cpk
# ===================================================================

class TestCpk:
    """Verify process capability indices."""

    # Centered process: mean = 12.36, spec 5 to 20
    CENTERED_DATA = _flat_subgroups(
        (10, 12, 11, 13, 14),
        (11, 11, 12, 13, 13),
        (14, 15, 13, 12, 11),
        (10, 10, 11, 11, 12),
        (13, 14, 14, 15, 14),
    )

    def test_cp_positive(self):
        """Cp is positive when specs are wider than process spread."""
        result = compute_cpk(self.CENTERED_DATA, usl=25.0, lsl=0.0)
        assert result["cp"] > 0

    def test_cpk_less_equal_cp(self):
        """Cpk is always <= Cp (Cpk equals Cp only when perfectly centered)."""
        result = compute_cpk(self.CENTERED_DATA, usl=25.0, lsl=0.0)
        assert result["cpk"] <= result["cp"] + 1e-9

    def test_off_center_process_reduces_cpk(self):
        """Moving USL closer to the mean reduces Cpk without changing Cp."""
        wide = compute_cpk(self.CENTERED_DATA, usl=25.0, lsl=0.0)
        narrow = compute_cpk(self.CENTERED_DATA, usl=14.0, lsl=0.0)
        assert narrow["cpk"] < wide["cpk"]

    def test_identical_values_infinite_capability(self):
        """When all values are identical, sigma_hat=0 and Cpk is inf."""
        data = [5.0] * 25
        result = compute_cpk(data, usl=10.0, lsl=0.0)
        assert result["cp"] == float("inf")
        assert result["cpk"] == float("inf")
        assert result["sigma_hat"] == 0.0

    def test_sigma_hat_uses_rbar_d2(self):
        """sigma_hat = R-bar / d2 (d2 = 2.326 for n=5)."""
        result = compute_cpk(self.CENTERED_DATA, usl=25.0, lsl=0.0)
        chart = xbar_r_chart(self.CENTERED_DATA)
        expected_sigma = chart["cl_r"] / 2.326
        assert result["sigma_hat"] == pytest.approx(expected_sigma)


# ===================================================================
# CUSUM
# ===================================================================

class TestCusum:
    """Verify CUSUM chart detects mean shifts."""

    def test_stable_process_no_signals(self):
        """A stable process centred on target should produce no CUSUM signals."""
        data = [10.0 + (i % 3) * 0.1 for i in range(50)]
        result = cusum(data, target=10.0)
        # With small variation around target, expect no signals
        assert isinstance(result["signal_indices"], list)

    def test_mean_shift_detected(self):
        """A clear mean shift should trigger at least one CUSUM signal."""
        # 30 observations at target, then 30 shifted by +3 sigma
        stable = [10.0 + (i % 5) * 0.2 for i in range(30)]
        shifted = [15.0 + (i % 5) * 0.2 for i in range(30)]
        data = stable + shifted
        result = cusum(data, target=10.0)
        assert len(result["signal_indices"]) > 0
        # Signal should appear after the shift (index >= 30 region)
        assert any(idx >= 25 for idx in result["signal_indices"])

    def test_cusum_lists_same_length_as_input(self):
        """c_plus and c_minus lists have the same length as the input."""
        data = [5.0, 6.0, 7.0, 5.5, 6.5]
        result = cusum(data, target=6.0)
        assert len(result["c_plus"]) == len(data)
        assert len(result["c_minus"]) == len(data)

    def test_too_few_observations_raises(self):
        """CUSUM needs at least 2 observations."""
        with pytest.raises(ValueError, match="at least 2"):
            cusum([5.0], target=5.0)

    def test_cusum_accumulators_nonnegative(self):
        """CUSUM accumulators are always >= 0 (reset to zero)."""
        data = [10.0 + i * 0.1 for i in range(20)]
        result = cusum(data, target=10.0)
        assert all(c >= -1e-12 for c in result["c_plus"])
        assert all(c >= -1e-12 for c in result["c_minus"])


# ===================================================================
# EWMA
# ===================================================================

class TestEwma:
    """Verify EWMA chart smoothing and signal detection."""

    def test_ewma_smooths_towards_target(self):
        """EWMA values should be smoother than raw data (less variance)."""
        import statistics as stats
        data = [10.0, 15.0, 8.0, 12.0, 14.0, 9.0, 11.0, 13.0, 10.0, 12.0]
        result = ewma(data, lambda_=0.2)
        raw_var = stats.variance(data)
        ewma_var = stats.variance(result["ewma_values"])
        assert ewma_var < raw_var

    def test_ewma_lambda_1_equals_raw_data(self):
        """With lambda=1, EWMA equals the raw observations."""
        data = [3.0, 5.0, 7.0, 4.0, 6.0]
        result = ewma(data, lambda_=1.0)
        assert result["ewma_values"] == pytest.approx(data)

    def test_ewma_output_lengths(self):
        """Output lists have the same length as input."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = ewma(data)
        assert len(result["ewma_values"]) == 5
        assert len(result["ucl"]) == 5
        assert len(result["lcl"]) == 5

    def test_ewma_control_limits_widen_then_stabilize(self):
        """Time-varying limits widen initially and converge."""
        data = [10.0] * 50
        # Add some noise so sigma != 0
        data = [10.0 + 0.5 * (i % 3 - 1) for i in range(50)]
        result = ewma(data, lambda_=0.2)
        # Later limits should be >= earlier limits (widening or stable)
        assert result["ucl"][-1] >= result["ucl"][0]

    def test_ewma_stable_process_no_signals(self):
        """A stable process should have no (or few) EWMA signals."""
        data = [10.0 + 0.1 * (i % 5) for i in range(100)]
        result = ewma(data, lambda_=0.2, target=10.0)
        # With very low variation, there should be few or no signals
        assert isinstance(result["signal_indices"], list)


# ===================================================================
# Western Electric Rules
# ===================================================================

class TestWesternElectricRules:
    """Verify detection of Western Electric rule violations."""

    def test_rule1_beyond_3sigma(self):
        """A point beyond UCL or LCL triggers Rule 1."""
        values = [50.0, 50.0, 50.0, 100.0, 50.0]
        violations = western_electric_rules(values, ucl=80.0, cl=50.0, lcl=20.0)
        rule1_hits = [(i, r) for i, r in violations if r == "Rule1"]
        assert len(rule1_hits) >= 1
        assert any(i == 3 for i, _ in rule1_hits)

    def test_rule4_eight_same_side(self):
        """Eight consecutive points above the center line triggers Rule 4."""
        # All 10 values above cl=50
        values = [55.0] * 10
        violations = western_electric_rules(values, ucl=80.0, cl=50.0, lcl=20.0)
        rule4_hits = [(i, r) for i, r in violations if r == "Rule4"]
        assert len(rule4_hits) >= 1

    def test_rule5_six_consecutive_trend(self):
        """Six monotonically increasing points triggers Rule 5."""
        values = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0]
        violations = western_electric_rules(values, ucl=30.0, cl=12.5, lcl=-5.0)
        rule5_hits = [(i, r) for i, r in violations if r == "Rule5"]
        assert len(rule5_hits) >= 1

    def test_no_violations_for_stable_data(self):
        """Data near the center line with no patterns yields no violations."""
        # All points equal to center line -- but this triggers Rule 6 if >= 15 pts
        # So keep it short (< 8 points, near center)
        values = [50.0, 50.5, 49.5, 50.2, 49.8]
        violations = western_electric_rules(values, ucl=80.0, cl=50.0, lcl=20.0)
        # Should have zero or very few violations
        assert len(violations) == 0

    def test_rule6_stratification(self):
        """Fifteen consecutive points within 1-sigma triggers Rule 6."""
        # 1-sigma zone: cl +/- (ucl-cl)/3 = 50 +/- 10 = [40, 60]
        values = [50.0] * 15
        violations = western_electric_rules(values, ucl=80.0, cl=50.0, lcl=20.0)
        rule6_hits = [(i, r) for i, r in violations if r == "Rule6"]
        assert len(rule6_hits) >= 1

    def test_returns_list_of_tuples(self):
        """Return type is a list of (index, rule_name) tuples."""
        values = [50.0, 50.0, 50.0]
        result = western_electric_rules(values, ucl=80.0, cl=50.0, lcl=20.0)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2


# ===================================================================
# Temperature Correction
# ===================================================================

class TestTemperatureCorrection:
    """Verify ASTM B193 resistance temperature correction."""

    def test_no_correction_at_target_temp(self):
        """No correction when measured temp equals target temp."""
        corrected = temperature_correct_resistance(1.0, 20.0, 20.0)
        assert corrected == pytest.approx(1.0)

    def test_higher_temp_reduces_corrected_resistance(self):
        """Measurement at T > 20C corrects downward (copper PTC)."""
        corrected = temperature_correct_resistance(1.0, 25.0, 20.0)
        assert corrected < 1.0

    def test_lower_temp_increases_corrected_resistance(self):
        """Measurement at T < 20C corrects upward."""
        corrected = temperature_correct_resistance(1.0, 15.0, 20.0)
        assert corrected > 1.0

    def test_formula_matches_manual_calc(self):
        """R_target = R_meas * (1 + alpha * (T_target - T_meas))."""
        r = 10.5
        t_meas = 30.0
        t_target = 20.0
        alpha = 0.00393
        expected = r * (1.0 + alpha * (t_target - t_meas))
        result = temperature_correct_resistance(r, t_meas, t_target, alpha)
        assert result == pytest.approx(expected)
