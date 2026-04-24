"""
Tests for engines/des_engine.py -- Discrete-Event Simulation Engine.

Covers closed-form queueing analytics (M/M/1, M/M/c, M/G/1),
Little's Law verification, DES simulation output structure,
event chronological ordering, and non-negative statistics.
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.des_engine import (
    QueueingAnalytics,
    SodhiCableDES,
    SimulationStatistics,
)


# ===================================================================
# M/M/1 Queue
# ===================================================================

class TestMM1:
    """Verify M/M/1 closed-form calculations."""

    def test_utilization(self):
        """rho = lambda / mu."""
        result = QueueingAnalytics.mm1(0.6, 1.0)
        assert result["rho"] == pytest.approx(0.6)

    def test_littles_law_L_equals_lambda_W(self):
        """Little's Law: L = lambda * W."""
        lam, mu = 0.6, 1.0
        result = QueueingAnalytics.mm1(lam, mu)
        assert result["L"] == pytest.approx(lam * result["W"])

    def test_littles_law_Lq_equals_lambda_Wq(self):
        """Little's Law for queue: Lq = lambda * Wq."""
        lam, mu = 0.6, 1.0
        result = QueueingAnalytics.mm1(lam, mu)
        assert result["Lq"] == pytest.approx(lam * result["Wq"])

    def test_known_mm1_values(self):
        """For lam=0.5, mu=1.0: rho=0.5, L=1, W=2."""
        result = QueueingAnalytics.mm1(0.5, 1.0)
        assert result["rho"] == pytest.approx(0.5)
        assert result["L"] == pytest.approx(1.0)
        assert result["W"] == pytest.approx(2.0)
        assert result["Lq"] == pytest.approx(0.5)
        assert result["Wq"] == pytest.approx(1.0)

    def test_stable_flag(self):
        """rho < 1 means stable=True."""
        result = QueueingAnalytics.mm1(0.8, 1.0)
        assert result["stable"] is True

    def test_unstable_when_rho_ge_1(self):
        """rho >= 1 returns stable=False with infinite metrics."""
        result = QueueingAnalytics.mm1(1.0, 1.0)
        assert result["stable"] is False
        assert result["L"] == float("inf")
        assert result["W"] == float("inf")

    def test_high_utilization_large_queue(self):
        """As rho approaches 1, queue length grows dramatically."""
        low = QueueingAnalytics.mm1(0.5, 1.0)
        high = QueueingAnalytics.mm1(0.95, 1.0)
        assert high["Lq"] > low["Lq"] * 10


# ===================================================================
# M/M/c Queue
# ===================================================================

class TestMMc:
    """Verify M/M/c closed-form calculations."""

    def test_mmc_utilization_formula(self):
        """rho = lambda / (c * mu)."""
        result = QueueingAnalytics.mmc(2.0, 1.0, 3)
        assert result["rho"] == pytest.approx(2.0 / 3.0)

    def test_mmc_littles_law(self):
        """L = lambda * W for M/M/c."""
        lam, mu, c = 2.0, 1.0, 3
        result = QueueingAnalytics.mmc(lam, mu, c)
        assert result["L"] == pytest.approx(lam * result["W"], abs=1e-6)

    def test_mmc_reduces_to_mm1_when_c_is_1(self):
        """M/M/1 is a special case of M/M/c with c=1."""
        mm1 = QueueingAnalytics.mm1(0.6, 1.0)
        mmc = QueueingAnalytics.mmc(0.6, 1.0, 1)
        assert mmc["L"] == pytest.approx(mm1["L"], abs=1e-6)
        assert mmc["W"] == pytest.approx(mm1["W"], abs=1e-6)

    def test_more_servers_reduces_waiting(self):
        """Adding servers reduces Wq."""
        r2 = QueueingAnalytics.mmc(1.5, 1.0, 2)
        r3 = QueueingAnalytics.mmc(1.5, 1.0, 3)
        assert r3["Wq"] < r2["Wq"]

    def test_mmc_unstable(self):
        """M/M/c with rho >= 1 is unstable."""
        result = QueueingAnalytics.mmc(6.0, 1.0, 3)  # rho = 2.0
        assert result["stable"] is False

    def test_erlang_c_probability(self):
        """Erlang-C P(wait) is between 0 and 1 for stable systems."""
        p = QueueingAnalytics.erlang_c(2.0, 1.0, 3)
        assert 0.0 <= p <= 1.0


# ===================================================================
# M/G/1 Queue
# ===================================================================

class TestMG1:
    """Verify M/G/1 Pollaczek-Khinchine formula."""

    def test_mg1_with_deterministic_service(self):
        """M/G/1 with sigma_s=0 (deterministic) has lower Lq than M/M/1."""
        mg1_det = QueueingAnalytics.mg1(0.5, 1.0, 0.0)
        mm1 = QueueingAnalytics.mm1(0.5, 1.0)
        assert mg1_det["Lq"] <= mm1["Lq"]

    def test_mg1_littles_law(self):
        """L = lambda * W for M/G/1."""
        lam = 0.5
        result = QueueingAnalytics.mg1(lam, 1.0, 0.5)
        assert result["L"] == pytest.approx(lam * result["W"], abs=1e-6)

    def test_mg1_coefficient_of_variation(self):
        """Cs = sigma_s / mean_service_time."""
        result = QueueingAnalytics.mg1(0.5, 2.0, 0.25)
        # mean_s = 1/mu = 0.5, Cs = 0.25 / 0.5 = 0.5
        assert result["Cs"] == pytest.approx(0.5)


# ===================================================================
# Little's Law Check
# ===================================================================

class TestLittlesLawCheck:
    """Verify the Little's Law verification helper."""

    def test_zero_residuals_for_exact_values(self):
        """Residuals are zero when L=lam*W exactly."""
        lam = 0.6
        result = QueueingAnalytics.mm1(lam, 1.0)
        check = QueueingAnalytics.littles_law_check(
            lam, result["L"], result["W"], result["Lq"], result["Wq"]
        )
        assert check["residual_L"] == pytest.approx(0.0, abs=1e-10)
        assert check["residual_Lq"] == pytest.approx(0.0, abs=1e-10)


# ===================================================================
# DES Simulation
# ===================================================================

class TestSodhiCableDES:
    """Verify the discrete-event simulation engine."""

    def test_simulation_completes(self):
        """Simulation runs to completion and returns results."""
        sim = SodhiCableDES({"n_jobs": 50, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        assert "completed_jobs" in results
        assert "stage_stats" in results
        assert "overall" in results

    def test_all_jobs_completed(self):
        """All requested jobs should complete (no breakdowns, no blocking)."""
        sim = SodhiCableDES({"n_jobs": 30, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        assert len(results["completed_jobs"]) == 30

    def test_events_in_chronological_order(self):
        """Completed jobs have arrival <= completion time."""
        sim = SodhiCableDES({"n_jobs": 50, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        for job in results["completed_jobs"]:
            assert job["arrival"] <= job["completion"]

    def test_flow_times_positive(self):
        """All flow times should be positive."""
        sim = SodhiCableDES({"n_jobs": 50, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        for job in results["completed_jobs"]:
            assert job["flow_time"] > 0

    def test_throughput_positive(self):
        """Overall throughput should be positive."""
        sim = SodhiCableDES({"n_jobs": 50, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        assert results["overall"]["throughput"] > 0

    def test_utilization_between_0_and_1(self):
        """Stage utilizations should be in [0, 1]."""
        sim = SodhiCableDES({"n_jobs": 100, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        for stage in results["stage_stats"]:
            assert 0.0 <= stage["utilization"] <= 1.0

    def test_queue_stats_nonnegative(self):
        """Average and max queue lengths should be non-negative."""
        sim = SodhiCableDES({"n_jobs": 50, "seed": 42, "breakdown_rate": 0.0})
        results = sim.run()
        for stage in results["stage_stats"]:
            assert stage["avg_queue"] >= 0.0
            assert stage["max_queue"] >= 0

    def test_deterministic_with_same_seed(self):
        """Two runs with the same seed produce identical throughput."""
        sim1 = SodhiCableDES({"n_jobs": 50, "seed": 123, "breakdown_rate": 0.0})
        sim2 = SodhiCableDES({"n_jobs": 50, "seed": 123, "breakdown_rate": 0.0})
        r1 = sim1.run()
        r2 = sim2.run()
        assert r1["overall"]["throughput"] == pytest.approx(
            r2["overall"]["throughput"]
        )

    def test_different_seeds_differ(self):
        """Different seeds produce different results (with high probability)."""
        sim1 = SodhiCableDES({"n_jobs": 100, "seed": 1, "breakdown_rate": 0.0})
        sim2 = SodhiCableDES({"n_jobs": 100, "seed": 9999, "breakdown_rate": 0.0})
        r1 = sim1.run()
        r2 = sim2.run()
        # Very unlikely to get identical flow times with different seeds
        assert r1["overall"]["avg_flow_time"] != r2["overall"]["avg_flow_time"]


# ===================================================================
# Sensitivity Sweep
# ===================================================================

class TestSensitivitySweep:
    """Verify the utilization sensitivity sweep."""

    def test_sweep_returns_list(self):
        """sensitivity_sweep returns a list of dicts."""
        results = QueueingAnalytics.sensitivity_sweep(1.0, 2)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_sweep_queue_increases_with_utilization(self):
        """Lq should increase as rho increases."""
        results = QueueingAnalytics.sensitivity_sweep(1.0, 1)
        for i in range(1, len(results)):
            assert results[i]["Lq"] >= results[i - 1]["Lq"] - 1e-6
