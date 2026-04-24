"""
SodhiCable MES — Live Demo Scenario Engine

Injects realistic manufacturing events into the operational database in real-time.
Each scenario plays out over 30-60 seconds with cascading effects visible across
the MES dashboards, SCADA, notifications, F8 process control, and F11 performance.

Usage: Call run_scenario(db_path, scenario_name) from an API endpoint.
The OPC-UA sim should be running for continuous sensor data backdrop.
"""
import sqlite3
import time
import random
import threading
from datetime import datetime

_active_scenario = None
_scenario_thread = None


SCENARIOS = {
    "spark_failure": {
        "name": "Spark Test Failure on CV-1",
        "description": "A pinhole is detected during insulation extrusion. Watch the MESA chain: F5 → F7 → F8 → F10.",
        "duration_sec": 45,
    },
    "cusum_drift": {
        "name": "CUSUM Drift on DRAW-1 Wire Diameter",
        "description": "Gradual die wear causes wire diameter to drift. CUSUM detects it before it goes OOC.",
        "duration_sec": 40,
    },
    "breakdown": {
        "name": "Unplanned Breakdown on PLCV-1",
        "description": "Motor failure on the PLCV caterpillar haul-off. Downtime logged, PM dispatched, OEE drops.",
        "duration_sec": 50,
    },
    "quality_crisis": {
        "name": "Compound Batch Contamination",
        "description": "Bad compound batch CB-0330 identified. Forward trace → quarantine affected lots → risk scoring.",
        "duration_sec": 55,
    },
    "shift_handover": {
        "name": "End of Shift + Report Generation",
        "description": "Day shift ends. OEE calculated, shift report generated, handoff created for Swing shift.",
        "duration_sec": 35,
    },
}


def _inject(db_path, table, values_dict):
    """Insert a row and return the row ID."""
    conn = sqlite3.connect(db_path)
    cols = ", ".join(values_dict.keys())
    placeholders = ", ".join(["?"] * len(values_dict))
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(values_dict.values()))
    conn.commit()
    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return rid


def _get_active_wo(db_path):
    """Get a random InProcess work order ID, or fall back to any WO."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    wo = conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status='InProcess' ORDER BY RANDOM() LIMIT 1").fetchone()
    if not wo:
        wo = conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status != 'Complete' ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return (wo["wo_id"], wo["product_id"]) if wo else ("WO-2026-002", "INST-3C16-FBS")


def _run_spark_failure(db_path, events):
    """Scenario: Spark test failure on CV-1."""
    wo_id, prod_id = _get_active_wo(db_path)
    events.append({"t": 0, "msg": f"CV-1 running {wo_id} ({prod_id}), insulation extrusion at 400 fpm..."})
    time.sleep(3)

    # Sensor readings showing normal operation
    events.append({"t": 3, "msg": "Sensor readings nominal: Temp=365°F, Speed=398 fpm, Tension=24.8 lbf"})
    for _ in range(3):
        _inject(db_path, "process_data_live", {"wc_id": "CV-1", "parameter": "Temperature_F", "value": round(random.gauss(365, 2), 1), "quality_flag": "Good"})
        _inject(db_path, "process_data_live", {"wc_id": "CV-1", "parameter": "Tension_lbf", "value": round(random.gauss(25, 1.5), 1), "quality_flag": "Good"})
    time.sleep(3)

    # Spark test FAIL
    events.append({"t": 6, "msg": "⚠ SPARK TEST FAIL — pinhole detected at 1,247 ft, voltage 3.2 kV"})
    _inject(db_path, "spark_test_log", {
        "wc_id": "TEST-1", "wo_id": wo_id, "reel_id": "R-4521",
        "voltage_kv": 3.2, "result": "FAIL", "footage_at_fault_ft": 1247,
    })
    time.sleep(3)

    # F8: Process deviation logged
    events.append({"t": 9, "msg": "F8: Critical process deviation logged — alarm triggered"})
    _inject(db_path, "process_deviations", {
        "wc_id": "CV-1", "wo_id": wo_id, "parameter_name": "SparkTest",
        "detection_method": "Threshold", "deviation_value": 0, "setpoint_value": 1,
        "severity": "Critical", "corrective_action": "Line stopped, hold placed",
    })
    time.sleep(3)

    # F7: NCR auto-created
    events.append({"t": 12, "msg": "F7: NCR auto-created — Spark_Fault, Critical severity"})
    _inject(db_path, "ncr", {
        "product_id": "INST-3C16-FBS", "wo_id": wo_id, "lot_number": "LOT-4502",
        "defect_type": "Spark_Fault", "description": "Spark test pinhole at 1,247 ft on CV-1, reel R-4521",
        "severity": "Critical", "detected_at": "CV-1", "status": "Open",
    })
    time.sleep(3)

    # F8: Hold placed
    events.append({"t": 15, "msg": "F8: Material hold placed — WO-2026-002 quarantined"})
    _inject(db_path, "hold_release", {
        "wo_id": wo_id, "lot_number": "LOT-4502",
        "hold_reason": "Critical spark test failure on CV-1, reel R-4521",
        "hold_status": "Active",
    })
    time.sleep(3)

    # F10: Forward trace initiated
    events.append({"t": 18, "msg": "F10: Forward trace from compound batch CB-0330 — identifying affected lots..."})
    time.sleep(3)

    # Scrap logged
    events.append({"t": 21, "msg": "F11: Scrap logged — 1,247 ft at CV-1, cause: SPARK_FAULT"})
    _inject(db_path, "scrap_log", {
        "wo_id": wo_id, "wc_id": "CV-1", "cause_code": "SPARK_FAULT",
        "quantity_ft": 1247, "cost": round(1247 * 0.85, 2), "disposition": "Scrap",
    })
    time.sleep(3)

    # Shift report impact
    events.append({"t": 24, "msg": "F11: OEE impacted — quality loss recorded, scrap Pareto updated"})
    _inject(db_path, "shift_reports", {
        "shift_date": datetime.now().strftime("%Y-%m-%d"), "shift_code": "Day", "wc_id": "CV-1",
        "oee_availability": 0.88, "oee_performance": 0.85, "oee_quality": 0.91,
        "oee_overall": round(0.88 * 0.85 * 0.91, 3),
        "total_output_ft": 3200, "total_scrap_ft": 1247, "total_downtime_min": 15,
    })
    time.sleep(3)

    # Audit trail
    events.append({"t": 27, "msg": "Audit trail: 6 entries logged (deviation, NCR, hold, scrap, shift report, lot trace)"})
    _inject(db_path, "audit_trail", {
        "table_name": "demo_scenario", "record_id": "spark_failure",
        "field_changed": "status", "old_value": "running", "new_value": "completed",
        "change_reason": "Spark failure scenario completed",
    })

    events.append({"t": 30, "msg": "✓ Scenario complete. Check: Dashboard (OEE), SCADA (CV-1), F8 (alarms), Notifications (bell)"})


def _run_cusum_drift(db_path, events):
    """Scenario: CUSUM detects gradual diameter drift on DRAW-1."""
    events.append({"t": 0, "msg": "DRAW-1 running — wire diameter nominal at 0.0253 in..."})
    time.sleep(3)

    # Normal readings, then drift
    for i in range(8):
        drift = 0 if i < 4 else 0.0002 * (i - 3)
        val = round(0.0253 + drift + random.gauss(0, 0.0002), 4)
        flag = "Good" if i < 5 else "Suspect" if i < 7 else "Bad"
        _inject(db_path, "process_data_live", {"wc_id": "DRAW-1", "parameter": "WireDiameter_in", "value": val, "quality_flag": flag})
        if i < 4:
            events.append({"t": i * 3, "msg": f"Reading {i+1}: diameter={val} in — nominal"})
        else:
            events.append({"t": i * 3, "msg": f"Reading {i+1}: diameter={val} in — DRIFTING ({'Suspect' if flag == 'Suspect' else '⚠ BAD'})"})
        time.sleep(3)

    # CUSUM signal
    events.append({"t": 24, "msg": "⚠ CUSUM signal: C⁺ exceeded threshold h=5.0 — sustained upward drift confirmed"})
    _inject(db_path, "process_deviations", {
        "wc_id": "DRAW-1", "wo_id": "WO-2026-014", "parameter_name": "WireDiameter_in",
        "detection_method": "CUSUM", "deviation_value": 0.0261, "setpoint_value": 0.0253,
        "severity": "Minor", "corrective_action": "Die replacement recommended",
    })
    time.sleep(3)

    # Maintenance dispatch
    events.append({"t": 27, "msg": "F9: Maintenance dispatched — corrective die replacement on DRAW-1"})
    _inject(db_path, "maintenance", {
        "equipment_id": 3, "wc_id": "DRAW-1", "maint_type": "Corrective",
        "scheduled_date": datetime.now().strftime("%Y-%m-%d"), "status": "Pending",
        "result": "Die replacement", "technician": "Tech-3",
    })
    _inject(db_path, "downtime_log", {
        "wc_id": "DRAW-1", "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "duration_min": 45, "category": "Breakdown", "cause": "Die wear — CUSUM drift detected",
    })
    time.sleep(3)

    events.append({"t": 30, "msg": "✓ Scenario complete. Check: SCADA (DRAW-1), F8 (CUSUM chart), F9 (maintenance), Notifications"})


def _run_breakdown(db_path, events):
    """Scenario: PLCV-1 caterpillar motor failure."""
    wo_id, prod_id = _get_active_wo(db_path)
    events.append({"t": 0, "msg": f"PLCV-1 running — jacketing operation on {wo_id}..."})
    time.sleep(3)

    events.append({"t": 3, "msg": "Caterpillar motor current trending high: 95A → 102A → 108A"})
    for kw in [110, 115, 120, 130]:
        _inject(db_path, "energy_readings", {"wc_id": "PLCV-1", "kw_draw": kw, "kwh_cumulative": kw * 1.68})
    time.sleep(3)

    events.append({"t": 6, "msg": "⚠ MOTOR TRIP — caterpillar haul-off EQ-PLCV-CAT stopped. Line down."})
    _inject(db_path, "downtime_log", {
        "wc_id": "PLCV-1", "start_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "duration_min": 90, "category": "Breakdown", "cause": "Caterpillar motor overload trip — EQ-PLCV-CAT",
    })
    time.sleep(3)

    events.append({"t": 9, "msg": "F9: Emergency maintenance dispatched for EQ-PLCV-CAT"})
    _inject(db_path, "maintenance", {
        "equipment_id": 26, "wc_id": "PLCV-1", "maint_type": "Corrective",
        "scheduled_date": datetime.now().strftime("%Y-%m-%d"), "status": "InProgress",
        "technician": "Tech-1",
    })
    time.sleep(5)

    events.append({"t": 14, "msg": "F11: OEE availability hit — 90 min unplanned downtime on PLCV-1"})
    # Generate multiple low-OEE reports to visibly move the plant average
    for wc in ["PLCV-1", "CV-1", "CABLE-1"]:
        _inject(db_path, "shift_reports", {
            "shift_date": datetime.now().strftime("%Y-%m-%d"), "shift_code": "Day", "wc_id": wc,
            "oee_availability": round(random.uniform(0.40, 0.55), 3),
            "oee_performance": round(random.uniform(0.60, 0.75), 3),
            "oee_quality": round(random.uniform(0.85, 0.92), 3),
            "oee_overall": round(random.uniform(0.20, 0.38), 3),
            "total_output_ft": random.randint(500, 1200),
            "total_scrap_ft": random.randint(200, 600),
            "total_downtime_min": random.randint(60, 120),
        })
    time.sleep(5)

    events.append({"t": 19, "msg": "Motor replaced. PLCV-1 restarting..."})
    time.sleep(5)

    events.append({"t": 24, "msg": "PLCV-1 back online. Downtime logged. OEE for this shift: 58.9%"})
    events.append({"t": 27, "msg": "✓ Scenario complete. Check: Dashboard (OEE drop), F9 (downtime), SCADA (PLCV-1), Executive (scrap $)"})


def _run_quality_crisis(db_path, events):
    """Scenario: Bad compound batch → forward trace → risk-scored quarantine."""
    events.append({"t": 0, "msg": "Lab report: Compound batch CB-0330 failed tensile test — potential contamination"})
    time.sleep(3)

    events.append({"t": 3, "msg": "F10: Initiating forward trace from CB-0330..."})
    time.sleep(2)

    events.append({"t": 5, "msg": "F10: 8 downstream lots identified across 3 tiers"})
    time.sleep(3)

    events.append({"t": 8, "msg": "F7: NCR created — Compound contamination, Critical severity"})
    _inject(db_path, "ncr", {
        "defect_type": "Material_Defect", "description": "Compound batch CB-0330 failed post-extrusion tensile test. Potential plasticizer contamination.",
        "severity": "Critical", "detected_at": "COMPOUND-1", "status": "Open",
    })
    time.sleep(3)

    events.append({"t": 11, "msg": "AI: Running risk-scored quarantine analysis..."})
    time.sleep(3)

    # Inject some process readings to differentiate lot risk
    for wc in ["CV-1", "CV-2", "PLCV-1"]:
        for _ in range(5):
            _inject(db_path, "process_data_live", {"wc_id": wc, "parameter": "Temperature_F", "value": round(random.gauss(370, 4), 1), "quality_flag": random.choice(["Good", "Good", "Suspect"])})

    events.append({"t": 14, "msg": "AI: 3 lots HIGH risk (spark failures + deviations), 2 MEDIUM, 3 LOW (all tests pass)"})
    events.append({"t": 17, "msg": "Recommendation: Release 3 LOW-risk lots immediately. Re-inspect 2 MEDIUM. Hold 3 HIGH."})
    time.sleep(3)

    # Hold the high-risk lots
    for wo in ["WO-2026-002", "WO-2026-005", "WO-2026-007"]:
        _inject(db_path, "hold_release", {
            "wo_id": wo, "hold_reason": f"Quality crisis: CB-0330 contamination — lot from {wo}",
            "hold_status": "Active",
        })
    time.sleep(3)

    events.append({"t": 20, "msg": "3 holds placed. 3 lots released. Quarantine scope reduced from 100% to 37.5%"})
    events.append({"t": 23, "msg": "✓ Scenario complete. Check: F10 (trace), AI (risk scores), F8 (holds), Notifications (3 new holds)"})


def _run_shift_handover(db_path, events):
    """Scenario: End of Day shift — report generation + handoff."""
    events.append({"t": 0, "msg": "14:30 — Day shift wrapping up. Generating end-of-shift reports..."})
    time.sleep(3)

    # Generate shift reports for active WCs
    for wc in ["CV-1", "CV-2", "DRAW-1", "STRAND-1", "PLCV-1", "CABLE-1", "TEST-1"]:
        a = round(random.uniform(0.82, 0.95), 3)
        p = round(random.uniform(0.84, 0.93), 3)
        q = round(random.uniform(0.95, 0.99), 3)
        oee = round(a * p * q, 3)
        _inject(db_path, "shift_reports", {
            "shift_date": datetime.now().strftime("%Y-%m-%d"), "shift_code": "Day", "wc_id": wc,
            "oee_availability": a, "oee_performance": p, "oee_quality": q, "oee_overall": oee,
            "total_output_ft": random.randint(1500, 4000), "total_scrap_ft": random.randint(50, 300),
            "total_downtime_min": random.randint(10, 60),
        })
    events.append({"t": 3, "msg": "F11: 7 shift reports generated. Plant OEE calculated."})
    time.sleep(3)

    events.append({"t": 6, "msg": "F6: Creating shift handoff — Day → Swing"})
    _inject(db_path, "shift_handoff", {
        "from_shift": "Day", "to_shift": "Swing",
        "handoff_date": datetime.now().strftime("%Y-%m-%d"),
        "from_operator": "EMP-001", "to_operator": "EMP-015",
        "machines_running": "CV-1,CV-2,DRAW-1,STRAND-1,PLCV-1,CABLE-1,TEST-1",
        "wos_in_progress": "WO-2026-002,WO-2026-005,WO-2026-007",
        "quality_issues": "CB-0330 compound hold active — 3 lots quarantined",
        "safety_alerts": "Wet floor near COMPOUND-1",
        "notes": "PLCV-1 caterpillar motor replaced at 10:30. Watch for vibration.",
        "status": "Pending",
    })
    time.sleep(3)

    events.append({"t": 9, "msg": "Handoff created. Key notes: compound hold active, PLCV motor replaced, wet floor alert."})
    events.append({"t": 12, "msg": "✓ Scenario complete. Check: F11 (new reports), Dashboard (OEE update), F6 (handoff), Executive (KPIs)"})


SCENARIO_RUNNERS = {
    "spark_failure": _run_spark_failure,
    "cusum_drift": _run_cusum_drift,
    "breakdown": _run_breakdown,
    "quality_crisis": _run_quality_crisis,
    "shift_handover": _run_shift_handover,
}


def run_scenario(db_path, scenario_name):
    """Run a scenario in a background thread. Returns immediately with scenario info."""
    global _active_scenario, _scenario_thread

    if scenario_name not in SCENARIOS:
        return {"error": f"Unknown scenario: {scenario_name}", "available": list(SCENARIOS.keys())}

    if _active_scenario:
        return {"error": f"Scenario '{_active_scenario}' already running. Wait for it to finish."}

    info = SCENARIOS[scenario_name]
    events = []
    _active_scenario = scenario_name

    def _run():
        global _active_scenario
        try:
            SCENARIO_RUNNERS[scenario_name](db_path, events)
        finally:
            _active_scenario = None

    _scenario_thread = threading.Thread(target=_run, daemon=True)
    _scenario_thread.start()

    return {
        "ok": True,
        "scenario": scenario_name,
        "name": info["name"],
        "description": info["description"],
        "duration_sec": info["duration_sec"],
    }


def get_status():
    """Return current scenario status."""
    return {
        "active": _active_scenario,
        "running": _active_scenario is not None,
        "available": {k: v for k, v in SCENARIOS.items()},
    }
