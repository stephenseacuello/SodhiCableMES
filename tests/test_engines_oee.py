"""
Tests for engines/oee.py -- Overall Equipment Effectiveness Engine.

Since compute_oee reads from a SQLite database, these tests create
in-memory databases with the required tables and seed data to verify
OEE = Availability x Performance x Quality, First-Pass Yield, and
the Six Big Losses breakdown.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.oee import (
    compute_oee,
    compute_fpy,
    compute_six_big_losses,
    compute_shift_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_oee_tables(conn):
    """Create the minimal tables that the OEE engine queries."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS shift_reports (
            id INTEGER PRIMARY KEY,
            wc_id TEXT,
            shift_date TEXT,
            oee_availability REAL,
            oee_performance REAL,
            oee_quality REAL,
            oee_overall REAL,
            total_output_ft REAL DEFAULT 0,
            total_scrap_ft REAL DEFAULT 0,
            total_downtime_min REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS downtime_log (
            id INTEGER PRIMARY KEY,
            wc_id TEXT,
            category TEXT,
            duration_min REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scrap_log (
            id INTEGER PRIMARY KEY,
            wc_id TEXT,
            cause_code TEXT,
            quantity_ft REAL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_steps (
            step_id TEXT,
            wc_id TEXT,
            defect_rate REAL DEFAULT 0
        )
    """)
    conn.commit()


def _oee_db():
    """Return a fresh in-memory connection with OEE tables."""
    conn = sqlite3.connect(":memory:")
    _create_oee_tables(conn)
    return conn


# ===================================================================
# OEE Calculation
# ===================================================================

class TestComputeOee:
    """Verify OEE = Availability x Performance x Quality."""

    def test_perfect_oee_from_shift_report(self):
        """100% A, P, Q in shift_reports yields OEE = 100.0."""
        conn = _oee_db()
        conn.execute(
            "INSERT INTO shift_reports "
            "(wc_id, shift_date, oee_availability, oee_performance, "
            "oee_quality, oee_overall, total_output_ft, total_scrap_ft, "
            "total_downtime_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("WC-01", "2026-04-22", 1.0, 1.0, 1.0, 1.0, 1000, 0, 0),
        )
        conn.commit()
        result = compute_oee(conn, "WC-01", "2026-04-22")
        assert result["oee"] == pytest.approx(100.0)
        conn.close()

    def test_zero_availability_yields_zero_oee(self):
        """When availability is 0, OEE must be 0."""
        conn = _oee_db()
        conn.execute(
            "INSERT INTO shift_reports "
            "(wc_id, shift_date, oee_availability, oee_performance, "
            "oee_quality, oee_overall, total_output_ft, total_scrap_ft, "
            "total_downtime_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("WC-01", "2026-04-22", 0.0, 1.0, 1.0, 0.0, 0, 0, 480),
        )
        conn.commit()
        result = compute_oee(conn, "WC-01", "2026-04-22")
        assert result["oee"] == pytest.approx(0.0)
        conn.close()

    def test_world_class_oee_threshold(self):
        """World-class OEE >= 85%.  Verify a realistic scenario hits it."""
        conn = _oee_db()
        # A=90%, P=95%, Q=99.5% => OEE ~= 85.1%
        oee_val = 0.90 * 0.95 * 0.995
        conn.execute(
            "INSERT INTO shift_reports "
            "(wc_id, shift_date, oee_availability, oee_performance, "
            "oee_quality, oee_overall, total_output_ft, total_scrap_ft, "
            "total_downtime_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("WC-01", "2026-04-22", 0.90, 0.95, 0.995, oee_val, 5000, 25, 48),
        )
        conn.commit()
        result = compute_oee(conn, "WC-01", "2026-04-22")
        assert result["oee"] >= 85.0
        conn.close()

    def test_realistic_cable_manufacturing_scenario(self):
        """A realistic shift: 92% availability, 88% performance, 97% quality."""
        conn = _oee_db()
        a, p, q = 0.92, 0.88, 0.97
        oee_val = a * p * q
        conn.execute(
            "INSERT INTO shift_reports "
            "(wc_id, shift_date, oee_availability, oee_performance, "
            "oee_quality, oee_overall, total_output_ft, total_scrap_ft, "
            "total_downtime_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("EXT-01", "2026-04-22", a, p, q, oee_val, 8000, 240, 38),
        )
        conn.commit()
        result = compute_oee(conn, "EXT-01", "2026-04-22")
        expected_pct = round(oee_val * 100, 1)
        assert result["oee"] == pytest.approx(expected_pct, abs=0.1)
        conn.close()

    def test_fallback_path_no_shift_report(self):
        """When no shift_report rows exist, fallback computes from raw tables."""
        conn = _oee_db()
        # No shift_reports, only downtime and scrap
        conn.execute(
            "INSERT INTO downtime_log (wc_id, category, duration_min) "
            "VALUES (?, ?, ?)",
            ("WC-01", "Breakdown", 60),
        )
        conn.execute(
            "INSERT INTO scrap_log (wc_id, cause_code, quantity_ft) "
            "VALUES (?, ?, ?)",
            ("WC-01", "Defect", 50),
        )
        conn.commit()
        result = compute_oee(conn, "WC-01", "2026-04-22")
        # Availability = (480 - 60) / 480 = 0.875
        assert result["availability"] == pytest.approx(0.875, abs=0.001)
        conn.close()

    def test_missing_work_center_returns_fallback(self):
        """Querying a non-existent work center returns fallback values."""
        conn = _oee_db()
        result = compute_oee(conn, "NONEXISTENT", "2026-04-22")
        # Should get a dict back (fallback path, no data)
        assert isinstance(result, dict)
        assert "availability" in result
        conn.close()


# ===================================================================
# First-Pass Yield
# ===================================================================

class TestComputeFpy:
    """Verify First-Pass Yield = product of (1 - defect_rate)."""

    def test_no_defects_yields_1(self):
        """FPY is 1.0 when there are no quality_steps rows."""
        conn = _oee_db()
        result = compute_fpy(conn)
        assert result == pytest.approx(1.0)
        conn.close()

    def test_single_step_fpy(self):
        """FPY with one step having 5% defect rate = 0.95."""
        conn = _oee_db()
        conn.execute(
            "INSERT INTO quality_steps (step_id, wc_id, defect_rate) "
            "VALUES (?, ?, ?)",
            ("S1", "WC-01", 0.05),
        )
        conn.commit()
        result = compute_fpy(conn, wc_id="WC-01")
        assert result == pytest.approx(0.95, abs=1e-6)
        conn.close()

    def test_multi_step_fpy(self):
        """FPY across 3 steps: (1-0.02)(1-0.03)(1-0.01) = 0.940794."""
        conn = _oee_db()
        for step_id, dr in [("S1", 0.02), ("S2", 0.03), ("S3", 0.01)]:
            conn.execute(
                "INSERT INTO quality_steps (step_id, wc_id, defect_rate) "
                "VALUES (?, ?, ?)",
                (step_id, "WC-01", dr),
            )
        conn.commit()
        result = compute_fpy(conn, wc_id="WC-01")
        expected = 0.98 * 0.97 * 0.99
        assert result == pytest.approx(expected, abs=1e-6)
        conn.close()


# ===================================================================
# Six Big Losses
# ===================================================================

class TestSixBigLosses:
    """Verify downtime/waste categorisation into the Six Big Losses."""

    def test_empty_returns_all_zeros(self):
        """No downtime or scrap yields all-zero loss categories."""
        conn = _oee_db()
        result = compute_six_big_losses(conn, "WC-01")
        assert all(v == 0.0 for v in result.values())
        conn.close()

    def test_breakdown_maps_to_equipment_failure(self):
        """Downtime category 'Breakdown' maps to equipment_failure."""
        conn = _oee_db()
        conn.execute(
            "INSERT INTO downtime_log (wc_id, category, duration_min) "
            "VALUES (?, ?, ?)",
            ("WC-01", "Breakdown", 45),
        )
        conn.commit()
        result = compute_six_big_losses(conn, "WC-01")
        assert result["equipment_failure"] == pytest.approx(45.0)
        conn.close()

    def test_setup_maps_to_setup_adjustment(self):
        """Downtime category 'Setup' maps to setup_adjustment."""
        conn = _oee_db()
        conn.execute(
            "INSERT INTO downtime_log (wc_id, category, duration_min) "
            "VALUES (?, ?, ?)",
            ("WC-01", "Setup", 30),
        )
        conn.commit()
        result = compute_six_big_losses(conn, "WC-01")
        assert result["setup_adjustment"] == pytest.approx(30.0)
        conn.close()


# ===================================================================
# Shift Report
# ===================================================================

class TestShiftReport:
    """Verify the aggregate shift report structure."""

    def test_shift_report_structure(self):
        """compute_shift_report returns all expected keys."""
        conn = _oee_db()
        result = compute_shift_report(conn, "WC-01", "A", "2026-04-22")
        assert "oee" in result
        assert "fpy" in result
        assert "six_big_losses" in result
        assert result["wc_id"] == "WC-01"
        assert result["shift_code"] == "A"
        assert result["shift_date"] == "2026-04-22"
        conn.close()
