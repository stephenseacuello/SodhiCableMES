"""ISA-95 Level 0-1: Field device and sensor data, PLC simulation.

SodhiCable MES — SCADA Blueprint
ISA-95 Level 1-2-3 drill-down: Plant Floor -> Work Center -> Sensor Detail.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("scada", __name__)


@bp.route("/scada")
def scada_page():
    return render_template("scada.html")


@bp.route("/api/scada/plant_overview")
def plant_overview():
    """Level 3 — full plant overview with status, alarms, parameters, and OEE."""
    from db import get_db
    db = get_db()

    # Main work-center + simulation state query
    rows = db.execute("""
        SELECT wc.wc_id, wc.name, wc.wc_type, wc.num_parallel,
               wc.capacity_ft_per_hr, wc.utilization_target, wc.isa_level,
               ss.status   AS sim_status,
               ss.current_job,
               ss.queue_length,
               ss.utilization AS sim_utilization
        FROM work_centers wc
        LEFT JOIN simulation_state ss ON ss.wc_id = wc.wc_id
        ORDER BY wc.wc_id
    """).fetchall()
    wcs = [dict(r) for r in rows]

    # Alarm counts & max severity per WC (unresolved deviations)
    alarm_rows = db.execute("""
        SELECT wc_id,
               COUNT(*)   AS alarm_count,
               MAX(CASE severity
                     WHEN 'Critical' THEN 4
                     WHEN 'Major'    THEN 3
                     WHEN 'Minor'    THEN 2
                     WHEN 'Warning'  THEN 1
                     ELSE 0 END) AS max_sev_rank,
               MAX(severity) AS max_severity
        FROM process_deviations
        WHERE resolved = 0
        GROUP BY wc_id
    """).fetchall()
    alarm_map = {}
    for a in alarm_rows:
        ad = dict(a)
        # Re-derive max_severity from rank for correct ordering
        rank = ad["max_sev_rank"] or 0
        sev_label = {4: "Critical", 3: "Major", 2: "Minor", 1: "Warning"}.get(rank, "Warning")
        alarm_map[ad["wc_id"]] = {
            "alarm_count": ad["alarm_count"],
            "max_severity": sev_label,
        }

    # Parameters tracked per WC
    param_rows = db.execute("""
        SELECT wc_id, parameter_name, source_level, collection_freq, uom
        FROM data_collection_points
        ORDER BY wc_id, parameter_name
    """).fetchall()
    param_map = {}
    for p in param_rows:
        pd = dict(p)
        param_map.setdefault(pd["wc_id"], []).append(pd)

    # Latest OEE per WC from shift_reports (most recent shift_date)
    oee_rows = db.execute("""
        SELECT sr.wc_id, sr.oee_overall, sr.oee_availability,
               sr.oee_performance, sr.oee_quality, sr.shift_date
        FROM shift_reports sr
        INNER JOIN (
            SELECT wc_id, MAX(shift_date) AS max_date
            FROM shift_reports
            GROUP BY wc_id
        ) latest ON sr.wc_id = latest.wc_id AND sr.shift_date = latest.max_date
    """).fetchall()
    oee_map = {}
    for o in oee_rows:
        od = dict(o)
        oee_map[od["wc_id"]] = {
            "oee_overall": od["oee_overall"],
            "oee_availability": od["oee_availability"],
            "oee_performance": od["oee_performance"],
            "oee_quality": od["oee_quality"],
            "shift_date": od["shift_date"],
        }

    # Assemble final list
    for wc in wcs:
        wid = wc["wc_id"]
        wc["alarms"] = alarm_map.get(wid, {"alarm_count": 0, "max_severity": None})
        wc["parameters"] = param_map.get(wid, [])
        wc["oee"] = oee_map.get(wid, None)

    return jsonify(wcs)


@bp.route("/api/scada/workcenter/<wc_id>")
def workcenter_detail(wc_id):
    """Level 2 — single work-center detail with equipment, recipe, live params, alarms, env, PM."""
    from db import get_db
    db = get_db()

    # WC info
    wc_row = db.execute("SELECT * FROM work_centers WHERE wc_id = ?", (wc_id,)).fetchone()
    if not wc_row:
        return jsonify({"error": f"Work center {wc_id} not found"}), 404
    wc_info = dict(wc_row)

    # Equipment
    eq_rows = db.execute("""
        SELECT * FROM equipment WHERE work_center_id = ? ORDER BY equipment_id
    """, (wc_id,)).fetchall()
    equipment = [dict(r) for r in eq_rows]

    # Active recipe with parameters
    recipe_row = db.execute("""
        SELECT * FROM recipes WHERE work_center_id = ? AND status = 'Approved'
        ORDER BY effective_date DESC LIMIT 1
    """, (wc_id,)).fetchone()
    recipe = None
    if recipe_row:
        recipe = dict(recipe_row)
        rp_rows = db.execute("""
            SELECT * FROM recipe_parameters WHERE recipe_id = ?
        """, (recipe["recipe_id"],)).fetchall()
        recipe["parameters"] = [dict(r) for r in rp_rows]

    # Live parameters — latest reading per parameter for this WC
    live_rows = db.execute("""
        SELECT pdl.reading_id, pdl.wc_id, pdl.parameter, pdl.value,
               pdl.timestamp, pdl.quality_flag
        FROM process_data_live pdl
        INNER JOIN (
            SELECT parameter, MAX(timestamp) AS max_ts
            FROM process_data_live
            WHERE wc_id = ?
            GROUP BY parameter
        ) latest ON pdl.parameter = latest.parameter
                 AND pdl.timestamp = latest.max_ts
        WHERE pdl.wc_id = ?
    """, (wc_id, wc_id)).fetchall()
    live_params = [dict(r) for r in live_rows]

    # Enrich live params with recipe setpoints & limits
    if recipe and recipe.get("parameters"):
        rp_map = {rp["parameter_name"]: rp for rp in recipe["parameters"]}
        for lp in live_params:
            rp = rp_map.get(lp["parameter"])
            if rp:
                lp["setpoint"] = rp.get("parameter_value")
                lp["lower_limit"] = rp.get("lower_limit")
                lp["upper_limit"] = rp.get("upper_limit")
                lp["uom"] = rp.get("uom")

    # Unresolved alarms
    alarm_rows = db.execute("""
        SELECT * FROM process_deviations
        WHERE wc_id = ? AND resolved = 0
        ORDER BY timestamp DESC
    """, (wc_id,)).fetchall()
    alarms = [dict(r) for r in alarm_rows]

    # Environmental — latest reading
    env_row = db.execute("""
        SELECT * FROM environmental_readings
        WHERE wc_id = ?
        ORDER BY timestamp DESC LIMIT 1
    """, (wc_id,)).fetchone()
    environmental = dict(env_row) if env_row else None

    # Upcoming maintenance
    maint_rows = db.execute("""
        SELECT ms.schedule_id, ms.equipment_id, ms.pm_type, ms.next_due,
               ms.assigned_to, ms.frequency_days,
               e.equipment_code, e.description AS equip_desc
        FROM maintenance_schedule ms
        JOIN equipment e ON e.equipment_id = ms.equipment_id
        WHERE e.work_center_id = ?
        ORDER BY ms.next_due ASC
        LIMIT 5
    """, (wc_id,)).fetchall()
    maintenance = [dict(r) for r in maint_rows]

    return jsonify({
        "wc_info": wc_info,
        "equipment": equipment,
        "recipe": recipe,
        "live_params": live_params,
        "alarms": alarms,
        "environmental": environmental,
        "maintenance": maintenance,
    })


@bp.route("/api/scada/sensor/<wc_id>/<parameter>")
def sensor_detail(wc_id, parameter):
    """Level 1 — sensor drill-down with readings, SPC, deviations, and config."""
    from db import get_db
    db = get_db()

    # Last 200 readings (returned chronologically)
    reading_rows = db.execute("""
        SELECT reading_id, wc_id, parameter, value, timestamp, quality_flag
        FROM process_data_live
        WHERE wc_id = ? AND parameter = ?
        ORDER BY timestamp DESC
        LIMIT 200
    """, (wc_id, parameter)).fetchall()
    readings = [dict(r) for r in reversed(reading_rows)]

    # Setpoint from active recipe
    sp_row = db.execute("""
        SELECT rp.parameter_value AS setpoint, rp.lower_limit, rp.upper_limit, rp.uom
        FROM recipe_parameters rp
        JOIN recipes r ON r.recipe_id = rp.recipe_id
        WHERE r.work_center_id = ? AND rp.parameter_name = ? AND r.status = 'Approved'
        ORDER BY r.effective_date DESC
        LIMIT 1
    """, (wc_id, parameter)).fetchone()
    setpoint = dict(sp_row) if sp_row else None

    # Latest SPC data
    spc_row = db.execute("""
        SELECT spc_id, measured_value, usl, lsl, ucl, cl, lcl,
               rule_violation, status, measurement_date
        FROM spc_readings
        WHERE wc_id = ? AND parameter_name = ?
        ORDER BY measurement_date DESC
        LIMIT 1
    """, (wc_id, parameter)).fetchone()
    spc = dict(spc_row) if spc_row else None

    # Recent deviations for this parameter
    dev_rows = db.execute("""
        SELECT deviation_id, deviation_value, setpoint_value, severity,
               corrective_action, timestamp, resolved
        FROM process_deviations
        WHERE wc_id = ? AND parameter_name = ?
        ORDER BY timestamp DESC
        LIMIT 20
    """, (wc_id, parameter)).fetchall()
    deviations = [dict(r) for r in dev_rows]

    # Collection config
    cfg_row = db.execute("""
        SELECT * FROM data_collection_points
        WHERE wc_id = ? AND parameter_name = ?
        LIMIT 1
    """, (wc_id, parameter)).fetchone()
    collection_config = dict(cfg_row) if cfg_row else None

    return jsonify({
        "readings": readings,
        "setpoint": setpoint,
        "spc": spc,
        "deviations": deviations,
        "collection_config": collection_config,
    })


@bp.route("/api/scada/energy/<wc_id>")
def scada_energy(wc_id):
    """Energy monitoring for a work center."""
    from db import get_db
    db = get_db()

    # Latest reading
    latest = db.execute(
        "SELECT kw_draw, kwh_cumulative, timestamp FROM energy_readings WHERE wc_id = ? ORDER BY timestamp DESC LIMIT 1",
        (wc_id,),
    ).fetchone()

    # Today's total kWh (sum of incremental kWh)
    today_kwh = db.execute("""
        SELECT ROUND(SUM(kw_draw * 1.68), 1) AS kwh_today
        FROM energy_readings
        WHERE wc_id = ? AND DATE(timestamp) = DATE('now')
    """, (wc_id,)).fetchone()

    # Recent trend (last 50 readings)
    trend = db.execute(
        "SELECT kw_draw, timestamp FROM energy_readings WHERE wc_id = ? ORDER BY timestamp DESC LIMIT 50",
        (wc_id,),
    ).fetchall()

    # kWh per KFT estimate (energy / output)
    output_row = db.execute(
        "SELECT COALESCE(SUM(total_output_ft), 1) AS total_ft FROM shift_reports WHERE wc_id = ?",
        (wc_id,),
    ).fetchone()
    total_kwh = db.execute(
        "SELECT COALESCE(SUM(kw_draw * 1.68), 0) AS total_kwh FROM energy_readings WHERE wc_id = ?",
        (wc_id,),
    ).fetchone()
    total_ft = output_row["total_ft"] if output_row else 1
    kwh_per_kft = round((total_kwh["total_kwh"] / max(total_ft, 1)) * 1000, 2) if total_kwh else 0

    return jsonify({
        "wc_id": wc_id,
        "current_kw": latest["kw_draw"] if latest else 0,
        "kwh_today": today_kwh["kwh_today"] if today_kwh else 0,
        "kwh_per_kft": kwh_per_kft,
        "trend": [{"kw": r["kw_draw"], "timestamp": r["timestamp"]} for r in reversed(trend)],
    })


@bp.route("/api/scada/plc_status/<wc_id>")
def scada_plc_status(wc_id):
    """Simulated PLC/controller status for a work center."""
    from db import get_db
    db = get_db()

    # Get tracked parameters with latest readings
    params = db.execute("""
        SELECT DISTINCT pdl.parameter,
               (SELECT pdl2.value FROM process_data_live pdl2
                WHERE pdl2.wc_id = pdl.wc_id AND pdl2.parameter = pdl.parameter
                ORDER BY pdl2.timestamp DESC LIMIT 1) AS actual_value,
               (SELECT pdl2.quality_flag FROM process_data_live pdl2
                WHERE pdl2.wc_id = pdl.wc_id AND pdl2.parameter = pdl.parameter
                ORDER BY pdl2.timestamp DESC LIMIT 1) AS quality_flag
        FROM process_data_live pdl
        WHERE pdl.wc_id = ?
        GROUP BY pdl.parameter
    """, (wc_id,)).fetchall()

    # Get recipe setpoints
    recipe_params = db.execute("""
        SELECT rp.parameter_name, rp.parameter_value AS setpoint,
               rp.lower_limit, rp.upper_limit, rp.uom
        FROM recipe_parameters rp
        JOIN recipes r ON r.recipe_id = rp.recipe_id
        WHERE r.work_center_id = ? AND r.status = 'Approved'
    """, (wc_id,)).fetchall()
    setpoints = {r["parameter_name"]: dict(r) for r in recipe_params}

    # Check for critical alarms (interlock trigger)
    critical = db.execute(
        "SELECT COUNT(*) AS c FROM process_deviations WHERE wc_id = ? AND resolved = 0 AND severity = 'Critical'",
        (wc_id,),
    ).fetchone()
    has_critical = (critical["c"] or 0) > 0

    loops = []
    for p in params:
        param_name = p["parameter"]
        actual = p["actual_value"]
        sp_info = setpoints.get(param_name)

        if sp_info and actual is not None:
            setpoint = sp_info["setpoint"]
            upper = sp_info["upper_limit"] or (setpoint * 1.1)
            lower = sp_info["lower_limit"] or (setpoint * 0.9)
            error = round(actual - setpoint, 4)
            range_val = upper - lower if upper != lower else 1
            output_pct = max(0, min(100, round(50 + (error / range_val) * 50, 1)))
            mode = "AUTO"
            interlock = "TRIPPED" if has_critical else "OK"
        else:
            setpoint = None
            error = None
            output_pct = None
            mode = "MANUAL"
            interlock = "OK"

        loops.append({
            "parameter": param_name,
            "mode": mode,
            "setpoint": setpoint,
            "actual": actual,
            "error": error,
            "output_pct": output_pct,
            "interlock": interlock,
            "quality_flag": p["quality_flag"],
            "uom": sp_info["uom"] if sp_info else None,
        })

    return jsonify({
        "wc_id": wc_id,
        "controller_mode": "AUTO" if any(l["mode"] == "AUTO" for l in loops) else "MANUAL",
        "interlock_status": "TRIPPED" if has_critical else "OK",
        "loops": loops,
    })


@bp.route("/api/scada/spark_tests/<wc_id>")
def scada_spark_tests(wc_id):
    """Return spark test results for a testing work center."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT log_id, reel_id, wo_id, footage_at_fault_ft, voltage_kv, result, timestamp
        FROM spark_test_log
        WHERE wc_id = ?
        ORDER BY timestamp DESC LIMIT 50
    """, (wc_id,)).fetchall()

    total = len(rows)
    passed = sum(1 for r in rows if r["result"] == "PASS")
    pass_rate = round(passed / max(total, 1) * 100, 1)

    return jsonify({
        "wc_id": wc_id,
        "total_tests": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": pass_rate,
        "tests": [dict(r) for r in rows],
    })
