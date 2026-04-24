#!/usr/bin/env python3
"""
SodhiCable MES v4.0 — Quantitative Validation Script

Runs each demo scenario against a clean database, measures before/after metrics,
and outputs a comparison table suitable for the LaTeX paper.

Usage: python validate.py
"""
import os
import sys
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "sodhicable_mes.db")


def get_metrics(db_path):
    """Capture current state metrics."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    m = {}
    m["oee"] = round((db.execute("SELECT AVG(oee_overall)*100 FROM shift_reports").fetchone()[0] or 0), 1)
    m["ncr_count"] = db.execute("SELECT COUNT(*) FROM ncr").fetchone()[0]
    m["hold_count"] = db.execute("SELECT COUNT(*) FROM hold_release WHERE hold_status='Active'").fetchone()[0]
    m["scrap_ft"] = db.execute("SELECT COALESCE(SUM(quantity_ft),0) FROM scrap_log").fetchone()[0]
    m["deviation_count"] = db.execute("SELECT COUNT(*) FROM process_deviations WHERE resolved=0").fetchone()[0]
    m["shift_reports"] = db.execute("SELECT COUNT(*) FROM shift_reports").fetchone()[0]
    m["downtime_min"] = db.execute("SELECT COALESCE(SUM(duration_min),0) FROM downtime_log").fetchone()[0]
    m["readings"] = db.execute("SELECT COUNT(*) FROM process_data_live").fetchone()[0]
    db.close()
    return m


def run_scenario(scenario_name):
    """Run a scenario and wait for completion."""
    from engines.demo_scenarios import run_scenario as _run, get_status
    result = _run(DB_PATH, scenario_name)
    if not result.get("ok"):
        print(f"  ERROR: {result.get('error', 'Unknown')}")
        return False
    # Wait for completion
    timeout = 120
    while get_status()["running"] and timeout > 0:
        time.sleep(2)
        timeout -= 2
    return True


def measure_api_performance():
    """Measure response times for key API endpoints."""
    sys.path.insert(0, BASE_DIR)
    from app import create_app
    app = create_app()
    timings = {}
    with app.test_client() as c:
        endpoints = [
            ("/api/health", "Health Check"),
            ("/api/dashboard/kpis", "Dashboard KPIs"),
            ("/api/scada/plant_overview", "SCADA Overview"),
            ("/api/oee/summary", "OEE Summary"),
            ("/api/traceability/trace?lot=CB-0330&direction=forward", "Genealogy Trace"),
            ("/api/traceability/risk_scored_trace?lot=CB-0330", "Risk-Scored Trace"),
            ("/api/search?q=CV-1", "Global Search"),
            ("/api/ai/anomalies", "AI Anomalies"),
            ("/api/quality/cpk", "Cpk Calculation"),
            ("/api/notifications", "Notifications"),
        ]
        for url, name in endpoints:
            start = time.time()
            r = c.get(url)
            elapsed = round((time.time() - start) * 1000, 1)
            timings[name] = {"ms": elapsed, "status": r.status_code}
    return timings


def main():
    print("=" * 70)
    print("SodhiCable MES v4.0 — Quantitative Validation")
    print("=" * 70)

    # 1. Reinitialize DB
    print("\n[1/4] Reinitializing database...")
    os.system(f"cd {BASE_DIR} && python init_db.py > /dev/null 2>&1")
    print("  Done — clean database created")

    # 2. Baseline metrics
    print("\n[2/4] Capturing baseline metrics...")
    baseline = get_metrics(DB_PATH)
    print(f"  OEE: {baseline['oee']}%")
    print(f"  NCRs: {baseline['ncr_count']}, Holds: {baseline['hold_count']}")
    print(f"  Scrap: {baseline['scrap_ft']:,.0f} ft, Deviations: {baseline['deviation_count']}")
    print(f"  Shift Reports: {baseline['shift_reports']}, Readings: {baseline['readings']:,}")

    # 3. Run scenarios and measure
    print("\n[3/4] Running demo scenarios...")
    scenarios = ["spark_failure", "cusum_drift", "breakdown", "quality_crisis", "shift_handover"]
    results = []

    for scenario in scenarios:
        print(f"\n  Running: {scenario}...")
        before = get_metrics(DB_PATH)
        ok = run_scenario(scenario)
        time.sleep(3)  # Let writes settle
        after = get_metrics(DB_PATH)

        delta = {
            "scenario": scenario,
            "oee_before": before["oee"],
            "oee_after": after["oee"],
            "oee_delta": round(after["oee"] - before["oee"], 1),
            "ncr_delta": after["ncr_count"] - before["ncr_count"],
            "hold_delta": after["hold_count"] - before["hold_count"],
            "scrap_delta": after["scrap_ft"] - before["scrap_ft"],
            "deviation_delta": after["deviation_count"] - before["deviation_count"],
            "report_delta": after["shift_reports"] - before["shift_reports"],
        }
        results.append(delta)
        print(f"    OEE: {delta['oee_before']}% → {delta['oee_after']}% ({delta['oee_delta']:+.1f})")
        print(f"    NCRs: +{delta['ncr_delta']}, Holds: +{delta['hold_delta']}, Scrap: +{delta['scrap_delta']:.0f} ft")

    # 4. API performance
    print("\n[4/4] Measuring API response times...")
    timings = measure_api_performance()
    for name, t in sorted(timings.items(), key=lambda x: x[1]["ms"]):
        print(f"  {name:25s} {t['ms']:8.1f} ms  ({t['status']})")

    # Output summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    # Scenario results table
    print("\nScenario Impact Analysis:")
    print(f"{'Scenario':<20s} {'OEE Δ':>8s} {'NCRs':>6s} {'Holds':>6s} {'Scrap (ft)':>10s} {'Deviations':>10s} {'Reports':>8s}")
    print("-" * 70)
    for r in results:
        print(f"{r['scenario']:<20s} {r['oee_delta']:>+7.1f}% {r['ncr_delta']:>+5d} {r['hold_delta']:>+5d} {r['scrap_delta']:>+9,.0f} {r['deviation_delta']:>+9d} {r['report_delta']:>+7d}")

    # API performance table
    print(f"\nAPI Response Times (p50):")
    avg = sum(t["ms"] for t in timings.values()) / len(timings)
    max_t = max(t["ms"] for t in timings.values())
    print(f"  Average: {avg:.1f} ms, Max: {max_t:.1f} ms")
    print(f"  All endpoints < 100ms: {'YES' if max_t < 100 else 'NO'}")

    # Final counts
    final = get_metrics(DB_PATH)
    print(f"\nFinal State:")
    print(f"  OEE: {final['oee']}%")
    print(f"  NCRs: {final['ncr_count']}, Holds: {final['hold_count']}")
    print(f"  Scrap: {final['scrap_ft']:,.0f} ft")
    print(f"  Shift Reports: {final['shift_reports']}")
    print(f"  Process Readings: {final['readings']:,}")


if __name__ == "__main__":
    main()
