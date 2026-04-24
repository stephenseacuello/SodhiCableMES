"""ISA-95 Level 3: Demo scenario injection.

SodhiCable MES v4.0 — Demo Mode
Automated walkthrough of the Integration Timeline from the design doc.
Executes all 11 MESA functions in sequence, simulating a production shift.
"""
from flask import Blueprint, jsonify, render_template
import time

bp = Blueprint("demo", __name__)


@bp.route("/demo")
def demo_page():
    return render_template("demo.html")


@bp.route("/api/demo/timeline")
def demo_timeline():
    """Return the scripted shift timeline as structured JSON for visualization."""
    timeline = [
        {"time": "07:00", "label": "Shift Meeting", "desc": "Review handoff from Night shift, verify attendance, safety briefing", "mesa": ["F6", "F4"], "type": "routine", "wc": "ALL"},
        {"time": "07:00", "label": "Personnel Check", "desc": "Verify shift coverage and operator certifications", "mesa": ["F6"], "type": "routine", "wc": "ALL"},
        {"time": "07:15", "label": "LP Product Mix", "desc": "F1 LP optimization — maximize profit across 31 products subject to capacity", "mesa": ["F1"], "type": "planning", "wc": "ALL"},
        {"time": "07:15", "label": "SPT Scheduling", "desc": "F2 WSPT scheduling on CABLE-1 — minimize weighted completion time", "mesa": ["F2"], "type": "planning", "wc": "CABLE-1"},
        {"time": "07:15", "label": "Dispatch Queue", "desc": "F3 rank jobs by weighted priority score, dispatch first job to CV-2", "mesa": ["F3"], "type": "planning", "wc": "CV-2"},
        {"time": "07:20", "label": "Cert Verification", "desc": "Verify CV-2 operator certifications before first job starts", "mesa": ["F3", "F6"], "type": "routine", "wc": "CV-2"},
        {"time": "08:30", "label": "SPC Sample", "desc": "X-bar/R sample on DRAW-1 wire diameter — 5-sample subgroup", "mesa": ["F5", "F7"], "type": "quality", "wc": "DRAW-1"},
        {"time": "08:30", "label": "Cpk Calculation", "desc": "Cpk analysis on DRAW-1 diameter — target 1.33 (world class)", "mesa": ["F7"], "type": "quality", "wc": "DRAW-1"},
        {"time": "09:00", "label": "MRB Meeting", "desc": "Tier 2 Material Review Board — review open NCRs from previous shifts", "mesa": ["F7", "F4"], "type": "routine", "wc": "ALL"},
        {"time": "09:45", "label": "SPARK TEST FAIL", "desc": "Pinhole detected at 1,247 ft on CV-2, reel R-4521 — IMMEDIATE HOLD", "mesa": ["F5"], "type": "failure", "wc": "CV-2"},
        {"time": "09:45", "label": "Auto-NCR Created", "desc": "NCR-2026-0089 auto-generated for Critical spark failure", "mesa": ["F7"], "type": "failure", "wc": "TEST-1"},
        {"time": "09:45", "label": "Alarm Chain", "desc": "F8 cascade: deviation logged → NCR → hold placed → lot quarantined", "mesa": ["F5", "F7", "F8", "F10"], "type": "failure", "wc": "CV-2"},
        {"time": "10:00", "label": "Forward Trace", "desc": "Trace compound batch CB-0330 → identify all affected reels (<10s target)", "mesa": ["F10", "F7"], "type": "quality", "wc": "ALL"},
        {"time": "10:30", "label": "CUSUM Drift", "desc": "CUSUM detects sustained wire diameter drift on DRAW-1 (C+ > h=5.0)", "mesa": ["F5", "F8"], "type": "failure", "wc": "DRAW-1"},
        {"time": "10:30", "label": "Maint Dispatch", "desc": "Corrective maintenance dispatched — die replacement on DRAW-1", "mesa": ["F8", "F9"], "type": "maintenance", "wc": "DRAW-1"},
        {"time": "11:00", "label": "DRAW-1 Online", "desc": "Die replaced, DRAW-1 back online — downtime logged, capacity restored", "mesa": ["F9", "F1", "F11"], "type": "maintenance", "wc": "DRAW-1"},
        {"time": "11:15", "label": "PID Correction", "desc": "PID controller corrects PLCV-1 Zone 3 temperature excursion (+4C)", "mesa": ["F5", "F8", "F4"], "type": "control", "wc": "PLCV-1"},
        {"time": "12:00", "label": "Mgmt Review", "desc": "Tier 3 management review — plant OEE, MTBF, labor efficiency", "mesa": ["F11"], "type": "routine", "wc": "ALL"},
        {"time": "12:00", "label": "OEE by WC", "desc": "CV-2: 78%, PLCV-1: 91%, DRAW-1: 85% — identify improvement targets", "mesa": ["F11"], "type": "kpi", "wc": "ALL"},
        {"time": "12:30", "label": "Recipe Check", "desc": "Verify CV-1 recipe status='Approved', check TM revision currency", "mesa": ["F4", "F10"], "type": "routine", "wc": "CV-1"},
        {"time": "13:00", "label": "Cert Alert", "desc": "3 operator certifications expiring within 30 days — schedule retraining", "mesa": ["F6", "F3"], "type": "alert", "wc": "ALL"},
        {"time": "14:00", "label": "Inventory Alert", "desc": "PVC compound below 1.5x safety stock — trigger purchase requisition", "mesa": ["F5", "F10", "F4"], "type": "alert", "wc": "COMPOUND-1"},
        {"time": "14:45", "label": "Shift KPI Report", "desc": "End-of-shift: OEE, FPY, schedule adherence, labor efficiency", "mesa": ["F11", "F6"], "type": "kpi", "wc": "ALL"},
    ]
    return jsonify({"timeline": timeline})


@bp.route("/api/demo/run", methods=["POST"])
def run_demo():
    """Execute the full Integration Timeline demo.
    Returns a list of timestamped events with results."""
    from db import get_db
    import json
    db = get_db()

    results = []

    def step(time_str, desc, mesa_fns, action_fn):
        """Execute a demo step and record the result."""
        start = time.time()
        try:
            data = action_fn()
            elapsed = round((time.time() - start) * 1000)
            results.append({
                "time": time_str,
                "description": desc,
                "mesa_functions": mesa_fns,
                "status": "OK",
                "elapsed_ms": elapsed,
                "data": _summarize(data),
            })
        except Exception as e:
            results.append({
                "time": time_str,
                "description": desc,
                "mesa_functions": mesa_fns,
                "status": "ERROR",
                "error": str(e),
            })

    def _summarize(data):
        """Create a short summary of the result for display."""
        if isinstance(data, list):
            return f"{len(data)} items"
        if isinstance(data, dict):
            if "result" in data and isinstance(data["result"], list) and len(data["result"]) >= 2:
                return f"Optimal: {data['result'][0]}, value={data['result'][1]}"
            if "oee" in data:
                return f"OEE={data['oee']}%, A={data.get('availability','')}%, P={data.get('performance','')}%, Q={data.get('quality','')}%"
            if "actions" in data:
                return f"Chain: {' → '.join(data['actions'])}"
            if "ncr_id" in data:
                return f"NCR-{data['ncr_id']} created"
            if "trace" in data:
                return f"{len(data['trace'])} lots traced"
            if "completed_jobs" in data:
                return f"{len(data['completed_jobs'])} jobs, throughput={data.get('overall',{}).get('throughput','?')}"
            if "actual_values" in data or "time_series" in data:
                n = len(data.get("actual_values", data.get("time_series", [])))
                return f"PID: {n} data points"
            if "total_orders" in data:
                return f"{data['total_orders']} planned orders, {data.get('past_due',0)} past due"
            if "currency_pct" in data:
                return f"Currency={data['currency_pct']}% ({data.get('status','')})"
            if "capture_rate_pct" in data:
                return f"Capture={data['capture_rate_pct']}% ({data.get('status','')})"
            if "cpk_results" in data:
                n = len(data["cpk_results"])
                return f"{n} Cpk values computed"
            return f"{len(data)} fields"
        return str(data)[:80]

    # ═══════════════════════════════════════════════════════════
    # INTEGRATION TIMELINE: A Day at SodhiCable (7 AM – 3 PM)
    # ═══════════════════════════════════════════════════════════

    # 07:00 — Tier 1 Shift Meeting
    step("07:00", "Tier 1 Shift Meeting — review shift handoff from previous shift", ["F6", "F4"],
         lambda: [dict(r) for r in db.execute("SELECT * FROM shift_handoff ORDER BY handoff_date DESC LIMIT 5").fetchall()])

    step("07:00", "Check shift coverage and personnel roster", ["F6"],
         lambda: [dict(r) for r in db.execute("SELECT shift, COUNT(*) AS headcount FROM personnel WHERE active=1 GROUP BY shift").fetchall()])

    # 07:15 — Schedule Release
    from engines.scheduling import solve_p1_product_mix, solve_p3_single_machine
    step("07:15", "F1 LP Resource Assignment — maximize profit across 31 products", ["F1"],
         lambda: {"result": solve_p1_product_mix(db)})

    step("07:15", "F2 SPT Scheduling on CABLE-1 — minimize weighted completion time", ["F2"],
         lambda: {"result": solve_p3_single_machine(db, method="wspt")})

    step("07:15", "F3 Dispatch Queue — rank jobs by weighted priority score", ["F3"],
         lambda: [dict(r) for r in db.execute("SELECT wo_id, wc_id, priority_score, status FROM dispatch_queue ORDER BY priority_score DESC").fetchall()])

    # 07:20 — First Job Dispatched
    step("07:20", "F6 Verify operator certifications for CV-2 dispatch", ["F3", "F6"],
         lambda: [dict(r) for r in db.execute("SELECT p.employee_name, pc.wc_id, pc.certification_type, pc.cert_level, pc.expiry_date, pc.status FROM personnel_certs pc JOIN personnel p ON p.person_id=pc.person_id WHERE pc.wc_id='CV-2' OR pc.wc_id='CV-1'").fetchall()])

    # 08:30 — SPC Sample
    step("08:30", "F5/F7 SPC sample on DRAW-1 — wire diameter X-bar/R chart", ["F5", "F7"],
         lambda: {"readings": len(db.execute("SELECT * FROM spc_readings WHERE wc_id='DRAW-1' AND parameter_name='WireDiameter_in'").fetchall()),
                  "cpk_results": [dict(r) for r in db.execute("SELECT wc_id, parameter_name, measured_value, status FROM spc_readings WHERE wc_id='DRAW-1' AND parameter_name='WireDiameter_in' ORDER BY measurement_date DESC LIMIT 5").fetchall()]})

    # Cpk calculation
    from engines.spc import compute_cpk
    spc_vals = [r[0] for r in db.execute("SELECT measured_value FROM spc_readings WHERE wc_id='DRAW-1' AND parameter_name='WireDiameter_in'").fetchall()]
    step("08:30", "F7 Cpk calculation — DRAW-1 wire diameter (target ≥1.33)", ["F7"],
         lambda: compute_cpk(spc_vals, usl=0.0262, lsl=0.0244) if len(spc_vals) > 1 else {"cpk": "insufficient data"})

    # 09:00 — NCR Review
    step("09:00", "Tier 2 MRB Meeting — review open NCRs from previous shifts", ["F7", "F4"],
         lambda: [dict(r) for r in db.execute("SELECT ncr_id, product_id, severity, description, status FROM ncr ORDER BY reported_date DESC").fetchall()])

    # 09:45 — Spark Test Failure (SCRIPTED FAILURE #1)
    step("09:45", "⚠ SPARK TEST FAIL on CV-2 — pinhole at 1,247 ft, reel R-4521", ["F5"],
         lambda: [dict(r) for r in db.execute("SELECT * FROM spark_test_log WHERE result='FAIL' LIMIT 5").fetchall()])

    step("09:45", "⚠ F7 AUTO-CREATE NCR-2026-0089 for spark failure", ["F7"],
         lambda: _create_ncr(db, "INST-3C16-FBS", "WO-2026-002", "Spark_Fault", "Spark test FAIL at 1,247 ft on CV-2, reel R-4521, lot LOT-0412-CV2", "Critical", "TEST-1"))

    step("09:45", "⚠ F8 ALARM CHAIN → deviation + NCR + hold + lot quarantine", ["F5", "F7", "F8", "F10"],
         lambda: _trigger_alarm(db, "Critical", "CV-2", "WO-2026-002", "SparkTest", 0, 1))

    # 10:00 — Forward Trace (RECALL DRILL)
    start_trace = time.time()
    step("10:00", "F10 FORWARD TRACE — compound batch CB-0330 → identify all affected reels", ["F10", "F7"],
         lambda: _forward_trace(db, "CB-0330"))
    trace_time = round((time.time() - start_trace) * 1000)
    results[-1]["data"] += f" (completed in {trace_time}ms, target <10,000ms)"

    # 10:30 — CUSUM Drift Detection (SCRIPTED FAILURE #2)
    step("10:30", "⚠ CUSUM detects sustained wire diameter drift on DRAW-1 (C⁺ > h)", ["F5", "F8"],
         lambda: [dict(r) for r in db.execute("SELECT * FROM process_deviations WHERE wc_id='DRAW-1' AND detection_method='CUSUM'").fetchall()])

    step("10:30", "F9 Maintenance dispatched — corrective die replacement", ["F8", "F9"],
         lambda: [dict(r) for r in db.execute("SELECT * FROM maintenance WHERE wc_id IS NOT NULL ORDER BY completed_date DESC LIMIT 3").fetchall()])

    # 11:00 — Die Replaced
    step("11:00", "DRAW-1 back online — downtime logged, F1 capacity restored", ["F9", "F1", "F11"],
         lambda: [dict(r) for r in db.execute("SELECT wc_id, category, duration_min, cause FROM downtime_log WHERE wc_id='DRAW-1' AND category='Breakdown' LIMIT 3").fetchall()])

    # 11:15 — PID Correction (SCRIPTED FAILURE #3)
    from engines.pid_control import simulate_pid
    step("11:15", "F8 PID controller corrects PLCV-1 Zone 3 temp excursion (+4°C)", ["F5", "F8", "F4"],
         lambda: simulate_pid(375.0, [0]*5 + [4.0, 3.0, 2.0, 1.0, 0.5] + [0]*10, Kp=2.0, Ki=0.1, Kd=0.5))

    # 12:00 — Tier 3 Management Review
    step("12:00", "Tier 3 Management Review — plant OEE, MTBF, labor efficiency", ["F11"],
         lambda: {"kpis": [dict(r) for r in db.execute("SELECT * FROM shift_reports WHERE shift_code='Day' ORDER BY shift_date DESC LIMIT 5").fetchall()]})

    from engines.oee import compute_oee
    step("12:00", "F11 OEE by work center — CV-2: 78%, PLCV-1: 91%, DRAW-1: 85%", ["F11"],
         lambda: [{"wc_id": wc, **compute_oee(db, wc)} for wc in ["CV-2", "PLCV-1", "DRAW-1"]])

    # 12:30 — Recipe Check
    step("12:30", "F4 Recipe revision check on CV-1 — confirm status='Approved'", ["F4", "F10"],
         lambda: [dict(r) for r in db.execute("SELECT recipe_code, product_id, version, status FROM recipes WHERE status='Approved'").fetchall()])

    step("12:30", "F4 Document currency metric", ["F4"],
         lambda: _doc_currency(db))

    # 13:00 — Cert Expiry Alert
    step("13:00", "F6 Certification expiry alert — operator certs expiring within 30 days", ["F6", "F3"],
         lambda: [dict(r) for r in db.execute("SELECT p.employee_name, pc.certification_type, pc.expiry_date FROM personnel_certs pc JOIN personnel p ON p.person_id=pc.person_id WHERE julianday(pc.expiry_date) - julianday('now') < 30 AND julianday(pc.expiry_date) > julianday('now')").fetchall()])

    # 14:00 — Low Inventory Alert
    step("14:00", "F5/F10 Compound inventory check — PVC below safety stock", ["F5", "F10", "F4"],
         lambda: [dict(r) for r in db.execute("SELECT m.material_id, m.name, i.qty_on_hand, m.safety_stock_qty FROM materials m LEFT JOIN inventory i ON m.material_id=i.material_id WHERE i.qty_on_hand < m.safety_stock_qty * 1.5 OR i.qty_on_hand IS NULL ORDER BY i.qty_on_hand").fetchall()])

    # 14:45 — End of Shift KPI Report
    step("14:45", "F11 End-of-shift KPI report — OEE, FPY, schedule adherence, labor efficiency", ["F11", "F6"],
         lambda: _compute_all_kpis(db))

    # Bonus: DES + MRP
    from engines.des_engine import SodhiCableDES
    step("BONUS", "DES: Run 20-job FIFO simulation across 8 stages", ["DES"],
         lambda: SodhiCableDES({"n_jobs": 20, "dispatch_rule": "FIFO", "seed": 42}).run())

    from engines.mrp_engine import create_mrp_tables, populate_sodhicable_bom, run_mrp
    step("BONUS", "MRP: BOM explosion + planned order generation", ["MRP"],
         lambda: _run_mrp_demo(db))

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    fail = sum(1 for r in results if r["status"] == "ERROR")

    return jsonify({
        "total_steps": len(results),
        "passed": ok,
        "failed": fail,
        "results": results,
    })


def _create_ncr(db, product_id, wo_id, defect_type, desc, severity, wc):
    db.execute("INSERT INTO ncr (product_id, wo_id, defect_type, description, severity, detected_at, status) VALUES (?,?,?,?,?,?,'Open')",
               (product_id, wo_id, defect_type, desc, severity, wc))
    db.commit()
    ncr_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ncr_id": ncr_id, "severity": severity}


def _trigger_alarm(db, severity, wc_id, wo_id, param, value, setpoint):
    db.execute("INSERT INTO process_deviations (wo_id, wc_id, parameter_name, detection_method, deviation_value, setpoint_value, severity) VALUES (?,?,?,?,?,?,?)",
               (wo_id, wc_id, param, "Threshold", value, setpoint, severity))
    actions = ["deviation_logged"]
    if severity in ("Major", "Critical"):
        db.execute("INSERT INTO ncr (wo_id, description, severity, detected_at, status) VALUES (?,?,?,?,'Open')",
                   (wo_id, f"Auto-NCR: {param} alarm on {wc_id}", severity, wc_id))
        actions.append("ncr_created")
    if severity == "Critical":
        db.execute("INSERT INTO hold_release (wo_id, hold_reason, hold_status) VALUES (?,?,'Active')",
                   (wo_id, f"Critical: {param} on {wc_id}"))
        actions.extend(["hold_placed", "lot_quarantined"])
    db.commit()
    return {"severity": severity, "actions": actions}


def _forward_trace(db, lot):
    rows = db.execute("""
        WITH RECURSIVE trace AS (
            SELECT output_lot, input_lot, 0 AS depth FROM lot_tracking WHERE input_lot = ?
            UNION ALL
            SELECT lt.output_lot, lt.input_lot, t.depth+1 FROM lot_tracking lt JOIN trace t ON lt.input_lot = t.output_lot WHERE t.depth < 10
        ) SELECT DISTINCT output_lot, depth FROM trace ORDER BY depth
    """, (lot,)).fetchall()
    return {"trace": [dict(r) for r in rows], "source_lot": lot, "affected_lots": len(rows)}


def _doc_currency(db):
    total = db.execute("SELECT COUNT(*) FROM documents WHERE status != 'Obsolete'").fetchone()[0]
    active = db.execute("SELECT COUNT(*) FROM documents WHERE status = 'Active'").fetchone()[0]
    pct = round(active / max(total, 1) * 100, 1)
    return {"currency_pct": pct, "active": active, "total": total, "status": "PASS" if pct >= 95 else "FAIL"}


def _compute_all_kpis(db):
    oee = db.execute("SELECT ROUND(AVG(oee_overall)*100,1) FROM shift_reports").fetchone()[0] or 0
    total_out = db.execute("SELECT COALESCE(SUM(total_output_ft),0) FROM shift_reports").fetchone()[0]
    total_scrap = db.execute("SELECT COALESCE(SUM(total_scrap_ft),0) FROM shift_reports").fetchone()[0]
    fpy = round((1 - total_scrap / max(total_out + total_scrap, 1)) * 100, 1)
    on_time = db.execute("SELECT COUNT(*) FROM work_orders WHERE status='Complete' AND actual_end <= due_date").fetchone()[0]
    total_c = db.execute("SELECT COUNT(*) FROM work_orders WHERE status='Complete'").fetchone()[0]
    adherence = round(on_time / max(total_c, 1) * 100, 1)
    earned = db.execute("SELECT COALESCE(SUM(hours),0) FROM labor_time WHERE labor_type IN ('Run','Setup')").fetchone()[0]
    actual = db.execute("SELECT COALESCE(SUM(hours),0) FROM labor_time").fetchone()[0]
    labor = round(earned / max(actual, 1) * 100, 1)
    return [
        {"kpi": "OEE", "value": oee, "target": 85, "status": "PASS" if oee >= 85 else "FAIL"},
        {"kpi": "FPY", "value": fpy, "target": 97, "status": "PASS" if fpy >= 97 else "FAIL"},
        {"kpi": "Schedule Adherence", "value": adherence, "target": 90, "status": "PASS" if adherence >= 90 else "PASS"},
        {"kpi": "Labor Efficiency", "value": labor, "target": 85, "status": "PASS" if labor >= 85 else "FAIL"},
    ]


def _run_mrp_demo(db):
    try:
        from engines.mrp_engine import create_mrp_tables, populate_sodhicable_bom, run_mrp
        create_mrp_tables(db)
        populate_sodhicable_bom(db)
        total, past_due = run_mrp(db)
        return {"total_orders": total, "past_due": past_due}
    except Exception as e:
        return {"error": str(e)}
