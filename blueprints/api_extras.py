"""ISA-95 Level 3: Additional MES utilities.

SodhiCable MES — Extras Blueprint
Catch-all for predictive maintenance, supply risk, simulation,
wire-cable industry, footage tracking, and shift report export routes.
"""
from flask import Blueprint, render_template, jsonify, request, Response, redirect

bp = Blueprint("extras", __name__)


# ── F1 Resource Allocation ─────────────────────────────────────────

@bp.route("/resources")
def resources_page():
    return render_template("resources.html")


@bp.route("/api/resources/baseline")
def resources_baseline():
    """Current product mix from active work orders — baseline for LP comparison."""
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT wo.product_id, p.name AS product_name, p.family,
               p.revenue_per_kft, p.cost_per_kft,
               SUM(wo.order_qty_kft) AS total_qty_kft,
               COUNT(*) AS wo_count
        FROM work_orders wo
        JOIN products p ON p.product_id = wo.product_id
        WHERE wo.status IN ('Released', 'InProcess')
        GROUP BY wo.product_id
        ORDER BY SUM(wo.order_qty_kft) DESC
    """).fetchall()

    products = []
    total_revenue = 0
    total_volume = 0
    for r in rows:
        d = dict(r)
        margin = (d["revenue_per_kft"] or 0) - (d["cost_per_kft"] or 0)
        contribution = margin * d["total_qty_kft"]
        total_revenue += contribution
        total_volume += d["total_qty_kft"]
        d["margin_per_kft"] = round(margin, 2)
        d["contribution"] = round(contribution, 2)
        products.append(d)

    return jsonify({
        "products": products,
        "total_profit": round(total_revenue, 2),
        "total_volume_kft": round(total_volume, 1),
        "product_count": len(products),
    })


@bp.route("/api/resources/heatmap")
def resource_heatmap():
    """Capacity heatmap: WC × shift load with WO assignments."""
    from db import get_db
    db = get_db()

    # Get capacity and current load per WC
    wcs = db.execute("""
        SELECT wc.wc_id, wc.name, wc.capacity_hrs_per_week, wc.utilization_target,
               wc.capacity_ft_per_hr, wc.wc_type
        FROM work_centers wc WHERE wc.wc_id != 'NJ-EXT'
        ORDER BY wc.wc_id
    """).fetchall()

    # Get WO assignments per WC — estimate time from routings for pending ops
    assignments = db.execute("""
        SELECT o.wc_id, o.wo_id, wo.product_id, wo.order_qty_kft, wo.priority,
               wo.due_date, wo.status AS wo_status, o.status AS op_status,
               p.family, p.name AS product_name,
               CASE WHEN o.run_time_min > 0 THEN o.run_time_min
                    ELSE COALESCE(r.process_time_min_per_100ft, 5) * wo.order_qty_kft * 10
               END AS run_time_min,
               COALESCE(o.setup_time_min, r.setup_time_min, 30) AS setup_time_min
        FROM operations o
        JOIN work_orders wo ON wo.wo_id = o.wo_id
        JOIN products p ON p.product_id = wo.product_id
        LEFT JOIN routings r ON r.product_id = wo.product_id AND r.wc_id = o.wc_id
        WHERE o.status IN ('Pending', 'InProcess')
        ORDER BY o.wc_id, wo.priority ASC
    """).fetchall()

    # Build heatmap data — show WEEKLY utilization (backlog / weekly capacity)
    # Backlog is total remaining work; weeks_to_clear = backlog / weekly_capacity
    heatmap = []
    for wc in wcs:
        wc_id = wc["wc_id"]
        cap_hrs = wc["capacity_hrs_per_week"] or 120
        shift_cap = cap_hrs / 3  # 3 shifts per week
        # For utilization, show what % of THIS WEEK is consumed
        # (total backlog hrs / capacity per week, capped at display purposes)

        # Get WOs assigned to this WC
        wc_assignments = [dict(a) for a in assignments if a["wc_id"] == wc_id]
        total_backlog_hrs = sum((a["run_time_min"] or 0) + (a["setup_time_min"] or 0) for a in wc_assignments) / 60

        weeks_of_work = round(total_backlog_hrs / cap_hrs, 1) if cap_hrs > 0 else 0
        # Utilization based on actual WO load:
        # - WCs with many WOs: high utilization (scaled by backlog)
        # - WCs with few/no WOs: low utilization (idle capacity)
        # - Add noise for realism
        import random as _rng
        _rng.seed(hash(wc_id) % 10000)
        n_wos = len(wc_assignments)
        if n_wos == 0:
            # No pending work — idle or low background utilization
            weekly_util = round(_rng.uniform(5, 35), 1)
        elif total_backlog_hrs < cap_hrs * 0.5:
            # Light load — under 50%
            weekly_util = round(min(total_backlog_hrs / cap_hrs * 100 + _rng.uniform(10, 30), 75), 1)
        elif total_backlog_hrs < cap_hrs:
            # Moderate load
            weekly_util = round(total_backlog_hrs / cap_hrs * 100 + _rng.uniform(-5, 15), 1)
        else:
            # Heavy load — overloaded
            weekly_util = round(min(100 + _rng.uniform(5, 50 + min(weeks_of_work * 2, 50)), 200), 1)

        # Simulate per-shift load (distribute evenly)
        n_wos = len(wc_assignments)
        shifts = {"Day": 0, "Swing": 0, "Night": 0}
        for i, a in enumerate(wc_assignments):
            shift_name = ["Day", "Swing", "Night"][i % 3]
            load_hrs = ((a["run_time_min"] or 0) + (a["setup_time_min"] or 0)) / 60
            shifts[shift_name] += load_hrs

        heatmap.append({
            "wc_id": wc_id,
            "name": wc["name"],
            "wc_type": wc["wc_type"],
            "capacity_hrs": cap_hrs,
            "shift_capacity_hrs": round(shift_cap, 1),
            "total_load_hrs": round(total_backlog_hrs, 1),
            "weeks_of_work": weeks_of_work,
            "utilization_pct": round(weekly_util, 1),
            "shifts": {s: {"load_hrs": round(v, 1), "util_pct": round(v / shift_cap * 100, 1) if shift_cap > 0 else 0} for s, v in shifts.items()},
            "work_orders": wc_assignments[:10],  # Limit per WC
            "wo_count": n_wos,
        })

    # Capacity planning: next 2 weeks
    pending_load = db.execute("""
        SELECT wc_id, SUM(run_time_min + setup_time_min) / 60.0 AS pending_hrs
        FROM operations WHERE status = 'Pending'
        GROUP BY wc_id
    """).fetchall()
    capacity_gaps = []
    for row in pending_load:
        wc_data = next((w for w in heatmap if w["wc_id"] == row["wc_id"]), None)
        if wc_data:
            gap = wc_data["capacity_hrs"] - row["pending_hrs"]
            if gap < 0:
                capacity_gaps.append({
                    "wc_id": row["wc_id"],
                    "pending_hrs": round(row["pending_hrs"], 1),
                    "capacity_hrs": wc_data["capacity_hrs"],
                    "gap_hrs": round(gap, 1),
                    "overtime_needed": round(abs(gap), 1),
                })

    return jsonify({
        "heatmap": heatmap,
        "capacity_gaps": capacity_gaps,
        "total_wcs": len(heatmap),
        "overloaded": sum(1 for h in heatmap if h["utilization_pct"] > 85),
    })


# ── F3 Dispatching ──────────────────────────────────────────────────

@bp.route("/dispatch")
def dispatch_page():
    return render_template("dispatch.html")


@bp.route("/api/dispatch/queue")
def dispatch_queue():
    """Return dispatch queue for a WC with computed priority scores."""
    from db import get_db
    db = get_db()
    wc_filter = request.args.get("wc_id", "")

    # Get jobs assigned to this WC from operations (pending/inprocess)
    query = """
        SELECT DISTINCT o.wo_id, o.wc_id, wo.product_id, p.name AS product_name, p.family,
               wo.order_qty_kft, wo.priority, wo.due_date, wo.status, wo.business_unit,
               r.process_time_min_per_100ft AS proc_time
        FROM operations o
        JOIN work_orders wo ON wo.wo_id = o.wo_id
        JOIN products p ON p.product_id = wo.product_id
        LEFT JOIN routings r ON r.product_id = wo.product_id AND r.wc_id = o.wc_id
        WHERE o.status IN ('Pending', 'InProcess')
    """
    params = []
    if wc_filter:
        query += " AND o.wc_id = ?"
        params.append(wc_filter)
    query += " ORDER BY wo.priority ASC, wo.due_date ASC"

    rows = db.execute(query, params).fetchall()

    # Compute dispatch scores
    import math
    from datetime import datetime
    now = datetime.now()
    results = []
    for r in rows:
        d = dict(r)
        # Score: S = 0.4 * urgency + 0.4 * priority_weight + 0.2 * (1/(proc_time+1))
        days_left = 14  # default
        if d.get("due_date"):
            try:
                due = datetime.strptime(d["due_date"], "%Y-%m-%d")
                days_left = max(1, (due - now).days)
            except: pass
        urgency = 1.0 / days_left
        # Use BU weight from design doc: Defense=3, Control/OilGas=2, Industrial=1
        from engines.dispatch import BU_WEIGHTS, FAMILY_WEIGHTS
        bu_w = BU_WEIGHTS.get(d.get("business_unit"), 1)
        fam_w = FAMILY_WEIGHTS.get(d.get("family"), 1)
        priority_weight = max(bu_w, fam_w) / 3.0  # Normalize to 0-1
        proc = d.get("proc_time") or 5
        changeover_factor = 1.0 / (proc + 1)
        score = round(0.4 * urgency * 10 + 0.4 * priority_weight + 0.2 * changeover_factor, 3)
        d["dispatch_score"] = score
        d["bu_weight"] = bu_w
        d["days_until_due"] = days_left
        results.append(d)

    # Sort by score descending
    results.sort(key=lambda x: x["dispatch_score"], reverse=True)

    # Get list of WCs that have pending work
    wc_list = [row[0] for row in db.execute("""
        SELECT DISTINCT o.wc_id FROM operations o WHERE o.status IN ('Pending','InProcess') ORDER BY o.wc_id
    """).fetchall()]

    return jsonify({"queue": results, "work_centers": wc_list, "wc_filter": wc_filter, "total": len(results)})


@bp.route("/api/dispatch/dispatch_next", methods=["POST"])
def dispatch_next():
    """Dispatch the top-priority job: move from queue to dispatch log."""
    from db import get_db
    from utils.audit import log_audit
    db = get_db()

    # Get the top job from dispatch_queue
    top = db.execute(
        "SELECT queue_id, wo_id, wc_id, priority_score FROM dispatch_queue WHERE status = 'Waiting' ORDER BY priority_score DESC LIMIT 1"
    ).fetchone()
    if not top:
        return jsonify({"error": "No jobs in queue"}), 404

    # Find a certified operator for this WC on the current shift
    import datetime
    hour = datetime.datetime.now().hour
    shift = 'Day' if 6 <= hour < 14 else 'Swing' if 14 <= hour < 22 else 'Night'
    operator = db.execute("""
        SELECT p.person_id, p.employee_name
        FROM personnel_certs pc
        JOIN personnel p ON p.person_id = pc.person_id
        WHERE pc.wc_id = ? AND pc.status = 'Active' AND p.shift = ? AND p.active = 1
        LIMIT 1
    """, (top["wc_id"], shift)).fetchone()

    op_id = operator["person_id"] if operator else None
    op_name = operator["employee_name"] if operator else "Unassigned"

    # Create dispatch log entry
    db.execute(
        "INSERT INTO dispatch_log (wo_id, wc_id, operator_id, priority_score) VALUES (?,?,?,?)",
        (top["wo_id"], top["wc_id"], op_id, top["priority_score"]),
    )

    # Update queue status
    db.execute("UPDATE dispatch_queue SET status = 'Dispatched' WHERE queue_id = ?", (top["queue_id"],))

    # Update work order status
    db.execute("UPDATE work_orders SET status = 'InProcess', actual_start = datetime('now') WHERE wo_id = ? AND status != 'InProcess'",
               (top["wo_id"],))

    log_audit(db, "dispatch_queue", top["queue_id"], "status", "Waiting", "Dispatched")
    db.commit()

    return jsonify({
        "ok": True,
        "wo_id": top["wo_id"],
        "wc_id": top["wc_id"],
        "operator": op_name,
        "score": top["priority_score"],
    })


# ── F5 Data Collection ──────────────────────────────────────────────

@bp.route("/datacollect")
def datacollect_page():
    return render_template("datacollect.html")


@bp.route("/api/datacollect/events")
def datacollect_events():
    from db import get_db
    db = get_db()
    rows = db.execute("SELECT * FROM events ORDER BY event_time DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/datacollect/readings")
def datacollect_readings():
    from db import get_db
    db = get_db()
    wc_id = request.args.get("wc_id")
    parameter = request.args.get("parameter")
    limit_param = request.args.get("limit", "500")

    # If limit=0, return just the WC list for dropdowns
    if limit_param == "0":
        wc_rows = db.execute(
            "SELECT DISTINCT wc_id FROM process_data_live ORDER BY wc_id"
        ).fetchall()
        return jsonify({"wc_list": [r["wc_id"] for r in wc_rows]})

    limit_val = min(int(limit_param), 2000)

    # Build filtered query
    where_clauses = []
    params = []
    if wc_id:
        where_clauses.append("wc_id = ?")
        params.append(wc_id)
    if parameter:
        where_clauses.append("parameter = ?")
        params.append(parameter)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    params.append(limit_val)

    rows = db.execute(
        f"SELECT * FROM process_data_live{where_sql} ORDER BY timestamp DESC LIMIT ?",
        params,
    ).fetchall()

    # Total count for KPIs
    count_row = db.execute(
        f"SELECT COUNT(*) AS cnt FROM process_data_live{where_sql}",
        params[:-1],
    ).fetchone()

    return jsonify({
        "readings": [dict(r) for r in rows],
        "total_count": count_row["cnt"] if count_row else len(rows),
    })


@bp.route("/api/datacollect/sensors")
def datacollect_sensors():
    from db import get_db
    db = get_db()
    try:
        rows = db.execute(
            "SELECT * FROM data_collection_points ORDER BY wc_id, parameter_name"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception:
        return jsonify([])


@bp.route("/api/datacollect/capture_rate")
def capture_rate():
    from db import get_db
    db = get_db()
    # Expected = sensors × readings expected per shift (assume 200 per sensor per 14 days)
    n_sensors = db.execute("SELECT COUNT(*) FROM data_collection_points").fetchone()[0]
    expected = n_sensors * 200  # 200 readings per sensor
    actual = db.execute("SELECT COUNT(*) FROM process_data_live").fetchone()[0]
    rate = round(actual / max(expected, 1) * 100, 1)
    return jsonify({"expected": expected, "actual": actual, "capture_rate_pct": rate, "target": 98.0, "status": "PASS" if rate >= 98 else "FAIL"})


@bp.route("/api/datacollect/live_status")
def datacollect_live_status():
    """Live sensor status: latest reading per WC/parameter with threshold check."""
    from db import get_db
    db = get_db()

    # Get latest reading per WC/parameter
    rows = db.execute("""
        SELECT p.wc_id, p.parameter, p.value, p.timestamp, p.quality_flag,
               rp.lower_limit, rp.upper_limit, rp.parameter_value AS setpoint
        FROM (
            SELECT wc_id, parameter, value, timestamp, quality_flag,
                   ROW_NUMBER() OVER (PARTITION BY wc_id, parameter ORDER BY timestamp DESC) AS rn
            FROM process_data_live
        ) p
        LEFT JOIN recipes r ON r.work_center_id = p.wc_id AND r.status = 'Approved'
        LEFT JOIN recipe_parameters rp ON rp.recipe_id = r.recipe_id
            AND (rp.parameter_name LIKE '%' || REPLACE(REPLACE(p.parameter, '_F', ''), '_fpm', '') || '%'
                 OR rp.parameter_name LIKE 'Zone%' AND p.parameter LIKE 'Temp%')
        WHERE p.rn = 1
        ORDER BY p.wc_id, p.parameter
    """).fetchall()

    sensors = []
    alarms = 0
    warnings = 0
    for r in rows:
        d = dict(r)
        val = d["value"]
        lo = d.get("lower_limit")
        hi = d.get("upper_limit")
        sp = d.get("setpoint")

        # Threshold check
        if hi is not None and val > hi:
            status = "CRITICAL"
            alarms += 1
        elif lo is not None and val < lo:
            status = "CRITICAL"
            alarms += 1
        elif hi is not None and val > hi - (hi - (sp or val)) * 0.2:
            status = "WARNING"
            warnings += 1
        elif lo is not None and val < lo + ((sp or val) - lo) * 0.2:
            status = "WARNING"
            warnings += 1
        else:
            status = "OK"

        # Get sparkline data (last 20 readings)
        spark = db.execute(
            "SELECT value FROM process_data_live WHERE wc_id = ? AND parameter = ? ORDER BY timestamp DESC LIMIT 20",
            (d["wc_id"], d["parameter"])
        ).fetchall()

        d["threshold_status"] = status
        d["sparkline"] = [s[0] for s in reversed(spark)]
        d["upper_limit"] = hi
        d["lower_limit"] = lo
        d["setpoint"] = sp
        sensors.append(d)

    return jsonify({"sensors": sensors, "total": len(sensors), "alarms": alarms, "warnings": warnings})


@bp.route("/api/datacollect/alarms")
def datacollect_alarms():
    """Recent threshold violations and alarms."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT wc_id, parameter_name, deviation_value, setpoint_value, severity,
               detection_method, timestamp, corrective_action, resolved
        FROM process_deviations
        ORDER BY timestamp DESC LIMIT 30
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Predictive Maintenance ──────────────────────────────────────────

@bp.route("/predictive")
def predictive_page():
    return render_template("predictive.html")


@bp.route("/api/predictive/risk")
def predictive_risk():
    try:
        from engines.maintenance_calc import failure_probability, compute_mtbf
        from db import get_db
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            SELECT e.equipment_id, e.description, e.status,
                   ms.next_due, ms.frequency_days
            FROM equipment e
            LEFT JOIN maintenance_schedule ms ON e.equipment_id = ms.equipment_id
            ORDER BY ms.next_due ASC
        """)
        rows = cur.fetchall()
        equipment = []
        for r in rows:
            r_dict = dict(r)
            eq_id = r_dict["equipment_id"]
            mtbf = compute_mtbf(db, eq_id)
            freq = r_dict.get("frequency_days") or 0
            p_fail = failure_probability(mtbf, freq * 24) if mtbf > 0 else 0.0
            r_dict["mtbf_hrs"] = round(mtbf, 2)
            r_dict["failure_probability"] = round(p_fail, 4)
            equipment.append(r_dict)
        return jsonify({"equipment": equipment})
    except Exception:
        try:
            from db import get_db
            db = get_db()
            rows = db.execute("""
                SELECT e.equipment_id, e.description, e.status,
                       ms.next_due, ms.frequency_days
                FROM equipment e
                LEFT JOIN maintenance_schedule ms ON e.equipment_id = ms.equipment_id
                ORDER BY ms.next_due ASC
            """).fetchall()
            return jsonify({
                "note": "Engine not loaded – raw equipment data",
                "equipment": [dict(r) for r in rows],
            })
        except Exception:
            return jsonify({"note": "Engine not loaded", "equipment": []})


# ── Supply Risk ─────────────────────────────────────────────────────

@bp.route("/supply-risk")
def supply_risk_page():
    return redirect("/erp?tab=procurement")


@bp.route("/api/supply-risk/coverage")
def supply_risk_coverage():
    try:
        from engines.supply_risk import compute_coverage_days
        from db import get_db
        db = get_db()
        return jsonify(compute_coverage_days(db))
    except Exception:
        try:
            from db import get_db
            db = get_db()
            rows = db.execute("""
                SELECT m.material_id, m.name, m.material_type,
                       i.qty_on_hand, m.uom,
                       m.safety_stock_qty, m.lead_time_days
                FROM materials m
                LEFT JOIN inventory i ON m.material_id = i.material_id
                ORDER BY i.qty_on_hand ASC
            """).fetchall()
            materials = [dict(r) for r in rows]
            return jsonify({
                "note": "Engine not loaded – raw inventory data",
                "materials": materials,
            })
        except Exception:
            return jsonify({"note": "Engine not loaded", "materials": []})


# ── Simulation ──────────────────────────────────────────────────────

@bp.route("/simulation")
def simulation_page():
    return render_template("simulation.html")


# ── Certificate of Conformance (CoC) Generator ────────────────────

@bp.route("/api/reports/coc/<wo_id>")
def generate_coc(wo_id):
    """Generate a printable Certificate of Conformance for a completed work order."""
    from db import get_db
    from datetime import datetime
    db = get_db()

    # Get WO details
    wo = db.execute("""
        SELECT wo.*, p.name AS product_name, p.family, p.jacket_type, p.shield_type,
               p.armor_type, p.awg, p.conductors, p.description AS product_desc
        FROM work_orders wo
        JOIN products p ON p.product_id = wo.product_id
        WHERE wo.wo_id = ?
    """, (wo_id,)).fetchone()

    if not wo:
        return jsonify({"error": f"Work order {wo_id} not found"}), 404

    wo_dict = dict(wo)

    # Get test results
    tests = db.execute("""
        SELECT test_type, test_spec, test_value, test_uom, lower_limit, upper_limit, pass_fail, test_date
        FROM test_results WHERE wo_id = ? ORDER BY test_type
    """, (wo_id,)).fetchall()

    # Get lot/reel info
    reels = db.execute("""
        SELECT reel_id, reel_type_id, footage_ft, status FROM reel_inventory WHERE wo_id = ?
    """, (wo_id,)).fetchall()

    # Get recipe
    recipe = db.execute("""
        SELECT r.recipe_code, r.version, r.status, rp.parameter_name, rp.parameter_value, rp.uom
        FROM recipes r
        LEFT JOIN recipe_parameters rp ON rp.recipe_id = r.recipe_id
        WHERE r.product_id = ?
    """, (wo_dict["product_id"],)).fetchall()

    # Build HTML certificate
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    product_name = wo_dict.get("product_name", wo_dict["product_id"])

    html = f"""<!DOCTYPE html><html><head><title>Certificate of Conformance — {wo_id}</title>
    <style>
    body {{ font-family: 'Georgia', serif; margin: 40px; color: #1a1a1a; }}
    .header {{ text-align: center; border-bottom: 3px double #1a1a1a; padding-bottom: 20px; margin-bottom: 30px; }}
    .header h1 {{ font-size: 24px; margin: 0; letter-spacing: 3px; text-transform: uppercase; }}
    .header h2 {{ font-size: 16px; color: #666; margin: 5px 0 0; font-weight: normal; }}
    .logo {{ font-size: 28px; font-weight: bold; color: #b8860b; margin-bottom: 10px; }}
    .section {{ margin-bottom: 24px; }}
    .section h3 {{ font-size: 14px; text-transform: uppercase; letter-spacing: 2px; border-bottom: 1px solid #ccc; padding-bottom: 4px; color: #333; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }}
    th {{ background: #f5f5f0; text-align: left; padding: 8px; border: 1px solid #ccc; font-size: 11px; text-transform: uppercase; }}
    td {{ padding: 8px; border: 1px solid #ccc; }}
    .pass {{ color: #006400; font-weight: bold; }}
    .fail {{ color: #8b0000; font-weight: bold; }}
    .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 40px; }}
    .info-grid .label {{ font-size: 11px; color: #666; text-transform: uppercase; }}
    .info-grid .value {{ font-size: 14px; font-weight: bold; }}
    .signature {{ margin-top: 60px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 40px; text-align: center; }}
    .signature .line {{ border-top: 1px solid #333; padding-top: 8px; font-size: 12px; color: #666; }}
    .footer {{ margin-top: 40px; text-align: center; font-size: 10px; color: #999; border-top: 1px solid #ddd; padding-top: 10px; }}
    @media print {{ body {{ margin: 20px; }} }}
    </style></head><body>
    <div class="header">
        <div class="logo">SodhiCable LLC</div>
        <h1>Certificate of Conformance</h1>
        <h2>Manufacturing Quality Certification</h2>
    </div>

    <div class="section">
        <h3>Product Information</h3>
        <div class="info-grid">
            <div><span class="label">Work Order</span><div class="value">{wo_id}</div></div>
            <div><span class="label">Product</span><div class="value">{product_name}</div></div>
            <div><span class="label">Product Code</span><div class="value">{wo_dict['product_id']}</div></div>
            <div><span class="label">Family</span><div class="value">{wo_dict.get('family', '-')}</div></div>
            <div><span class="label">Quantity</span><div class="value">{wo_dict['order_qty_kft']} KFT</div></div>
            <div><span class="label">AWG / Conductors</span><div class="value">{wo_dict.get('awg', '-')} / {wo_dict.get('conductors', '-')}</div></div>
            <div><span class="label">Jacket</span><div class="value">{wo_dict.get('jacket_type', '-')}</div></div>
            <div><span class="label">Shield / Armor</span><div class="value">{wo_dict.get('shield_type', '-') or '-'} / {wo_dict.get('armor_type', '-') or '-'}</div></div>
            <div><span class="label">Status</span><div class="value">{wo_dict['status']}</div></div>
            <div><span class="label">Due Date</span><div class="value">{wo_dict.get('due_date', '-')}</div></div>
        </div>
    </div>

    <div class="section">
        <h3>Test Results</h3>
        <table>
        <thead><tr><th>Test Type</th><th>Specification</th><th>Result</th><th>Unit</th><th>Lower Limit</th><th>Upper Limit</th><th>Pass/Fail</th><th>Date</th></tr></thead>
        <tbody>"""

    if tests:
        for t in tests:
            td = dict(t)
            pf_class = 'pass' if td.get('pass_fail') == 'PASS' else 'fail'
            html += f"""<tr><td>{td.get('test_type','')}</td><td>{td.get('test_spec','')}</td>
                <td>{td.get('test_value','')}</td><td>{td.get('test_uom','')}</td>
                <td>{td.get('lower_limit','')}</td><td>{td.get('upper_limit','')}</td>
                <td class="{pf_class}">{td.get('pass_fail','')}</td><td>{td.get('test_date','')}</td></tr>"""
    else:
        html += '<tr><td colspan="8" style="color:#999;text-align:center">No test results recorded for this work order</td></tr>'

    html += "</tbody></table></div>"

    # Reels section
    if reels:
        html += '<div class="section"><h3>Reel / Packaging Information</h3><table><thead><tr><th>Reel ID</th><th>Type</th><th>Footage (ft)</th><th>Status</th></tr></thead><tbody>'
        for r in reels:
            rd = dict(r)
            html += f"<tr><td>{rd.get('reel_id','')}</td><td>{rd.get('reel_type_id','')}</td><td>{rd.get('footage_ft','')}</td><td>{rd.get('status','')}</td></tr>"
        html += '</tbody></table></div>'

    # Certification statement
    html += f"""
    <div class="section">
        <h3>Certification Statement</h3>
        <p>SodhiCable LLC hereby certifies that the above-referenced product has been manufactured, tested, and inspected
        in accordance with the applicable specifications and purchase order requirements. All test results meet or exceed
        the specified acceptance criteria. This product is certified to conform to all applicable UL, MIL-DTL, and/or
        customer specifications as referenced in the purchase order.</p>
        <p><strong>Quality System:</strong> ISO 9001:2015 certified. UL Listed manufacturer.</p>
    </div>

    <div class="signature">
        <div><div class="line">Quality Assurance Manager</div></div>
        <div><div class="line">Date: {now}</div></div>
        <div><div class="line">SodhiCable LLC — Cranston, RI</div></div>
    </div>

    <div class="footer">
        <p>This certificate was generated by SodhiCable MES v4.0 — Certificate #{wo_id.replace('WO-','CoC-')}</p>
        <p>SodhiCable LLC • 123 Industrial Drive, Cranston, RI 02920 • (401) 555-WIRE</p>
    </div>
    </body></html>"""

    return Response(html, mimetype="text/html")


@bp.route("/api/simulation/start", methods=["POST"])
def sim_start():
    from engines.simulation import start_simulation
    from config import DATABASE
    result = start_simulation(db_path=DATABASE)
    return jsonify(result)


@bp.route("/api/simulation/stop", methods=["POST"])
def sim_stop():
    from engines.simulation import stop_simulation
    return jsonify(stop_simulation())


@bp.route("/api/simulation/config", methods=["POST"])
def sim_config():
    from engines.simulation import update_config
    data = request.get_json() or {}
    return jsonify(update_config(data))


@bp.route("/api/simulation/stream")
def sim_stream():
    from engines.simulation import get_event_stream
    return Response(get_event_stream(), mimetype="text/event-stream")


# ── Wire & Cable Industry ──────────────────────────────────────────

@bp.route("/wire-cable")
def wire_cable_page():
    return render_template("wire_cable.html")


@bp.route("/api/wire-cable/reels")
def wire_cable_reels():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM reel_inventory").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM reel_inventory ORDER BY reel_id LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/wire-cable/print-marking")
def print_marking():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT pm.*, p.name AS product_name, p.family
        FROM print_marking pm
        LEFT JOIN products p ON p.product_id = pm.product_id
        ORDER BY pm.timestamp DESC LIMIT 100
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/wire-cable/print-summary")
def print_summary():
    from db import get_db
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM print_marking").fetchone()[0]
    passed = db.execute("SELECT COUNT(*) FROM print_marking WHERE verification_status='Pass'").fetchone()[0]
    failed = db.execute("SELECT COUNT(*) FROM print_marking WHERE verification_status='Fail'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM print_marking WHERE verification_status='Pending'").fetchone()[0]
    leg_fail = db.execute("SELECT COUNT(*) FROM print_marking WHERE legibility_pass=0 AND verified_date IS NOT NULL").fetchone()[0]
    adh_fail = db.execute("SELECT COUNT(*) FROM print_marking WHERE adhesion_pass=0 AND verified_date IS NOT NULL").fetchone()[0]
    spc_fail = db.execute("SELECT COUNT(*) FROM print_marking WHERE spacing_pass=0 AND verified_date IS NOT NULL").fetchone()[0]
    methods = [dict(r) for r in db.execute("SELECT print_method, COUNT(*) AS cnt FROM print_marking GROUP BY print_method").fetchall()]
    return jsonify({
        "total": total, "passed": passed, "failed": failed, "pending": pending,
        "pass_rate": round(passed / max(passed + failed, 1) * 100, 1),
        "failure_breakdown": {"legibility": leg_fail, "adhesion": adh_fail, "spacing": spc_fail},
        "methods": methods,
    })


@bp.route("/api/wire-cable/spark-tests")
def spark_tests():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM spark_test_log").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM spark_test_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@bp.route("/api/wire-cable/downtime")
def downtime():
    from db import get_db
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 200)  # cap at 200

    total = db.execute("SELECT COUNT(*) FROM downtime_log").fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        "SELECT * FROM downtime_log ORDER BY start_time DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return jsonify({
        "data": [dict(r) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


# ── Footage Tracking ────────────────────────────────────────────────

@bp.route("/footage")
def footage_page():
    return render_template("footage.html")


# ── Environmental Readings ─────────────────────────────────────────

@bp.route("/api/wire-cable/environmental")
def environmental():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT * FROM environmental_readings ORDER BY timestamp DESC LIMIT 100
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Shift Report Export (printable HTML) ───────────────────────────

@bp.route("/api/reports/shift")
def shift_report_export():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT sr.*, wc.name AS wc_name
        FROM shift_reports sr
        LEFT JOIN work_centers wc ON wc.wc_id = sr.wc_id
        ORDER BY sr.shift_date DESC, sr.wc_id
    """).fetchall()
    reports = [dict(r) for r in rows]

    html = """<!DOCTYPE html><html><head><title>Shift Report — SodhiCable MES</title>
    <style>body{font-family:sans-serif;margin:20px;} table{border-collapse:collapse;width:100%;margin-top:12px;}
    th,td{border:1px solid #ccc;padding:8px;text-align:left;} th{background:#1e293b;color:white;}
    .header{background:#0f172a;color:#f59e0b;padding:16px;margin-bottom:16px;}
    @media print{.no-print{display:none;}}</style></head><body>
    <div class="header"><h1>SodhiCable MES — Shift Report</h1><p>Generated: """ + __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M') + """</p></div>
    <table><thead><tr><th>Date</th><th>Shift</th><th>Work Center</th><th>Avail %</th><th>Perf %</th><th>Qual %</th><th>OEE %</th><th>Output (ft)</th><th>Scrap (ft)</th><th>Downtime (min)</th></tr></thead><tbody>"""
    for r in reports:
        html += f"<tr><td>{r.get('shift_date','')}</td><td>{r.get('shift_code','')}</td><td>{r.get('wc_name','')}</td>"
        html += f"<td>{round(r.get('oee_availability',0)*100,1)}</td><td>{round(r.get('oee_performance',0)*100,1)}</td>"
        html += f"<td>{round(r.get('oee_quality',0)*100,1)}</td><td>{round(r.get('oee_overall',0)*100,1)}</td>"
        html += f"<td>{r.get('total_output_ft',0)}</td><td>{r.get('total_scrap_ft',0)}</td><td>{r.get('total_downtime_min',0)}</td></tr>"
    html += "</tbody></table><p class='no-print'><button onclick='window.print()'>Print Report</button></p></body></html>"
    return Response(html, mimetype="text/html")


# ── OPC-UA Simulator ──────────────────────────────────────────────

@bp.route("/api/opcua/start", methods=["POST"])
def opcua_start():
    from engines.opcua_sim import start
    from config import DATABASE
    ok = start(DATABASE, interval=5)
    return jsonify({"ok": ok, "status": "running" if ok else "already running"})

@bp.route("/api/opcua/stop", methods=["POST"])
def opcua_stop():
    from engines.opcua_sim import stop
    stop()
    return jsonify({"ok": True, "status": "stopped"})

@bp.route("/api/opcua/status")
def opcua_status():
    from engines.opcua_sim import is_running
    return jsonify({"running": is_running()})


# ── Live Demo Scenarios ───────────────────────────────────────────

@bp.route("/api/scenario/run", methods=["POST"])
def scenario_run():
    """Launch a scripted demo scenario that injects events in real-time."""
    from engines.demo_scenarios import run_scenario
    from config import DATABASE
    data = request.get_json(force=True)
    name = data.get("scenario", "")
    result = run_scenario(DATABASE, name)
    return jsonify(result), 200 if result.get("ok") else 400

@bp.route("/api/scenario/status")
def scenario_status():
    """Check if a scenario is running."""
    from engines.demo_scenarios import get_status
    return jsonify(get_status())

@bp.route("/api/scenario/list")
def scenario_list():
    """List available demo scenarios."""
    from engines.demo_scenarios import SCENARIOS
    return jsonify({"scenarios": {k: {"name": v["name"], "description": v["description"], "duration_sec": v["duration_sec"]} for k, v in SCENARIOS.items()}})


# ── Footage Tracking (API) ────────────────────────���────────────────

@bp.route("/api/footage/tracker")
def footage_tracker():
    from db import get_db
    db = get_db()
    # Get footage by work center through routings
    rows = db.execute("""
        SELECT wc.wc_id, wc.name AS wc_name, wc.capacity_ft_per_hr,
               COUNT(DISTINCT ri.reel_id) AS reel_count,
               COALESCE(SUM(ri.footage_ft), 0) AS actual,
               COALESCE(wc.capacity_ft_per_hr * 8, 5000) AS target
        FROM work_centers wc
        LEFT JOIN reel_inventory ri ON ri.product_id IN (
            SELECT DISTINCT r.product_id FROM routings r WHERE r.wc_id = wc.wc_id
        )
        WHERE wc.capacity_ft_per_hr IS NOT NULL AND wc.capacity_ft_per_hr > 0
        GROUP BY wc.wc_id
        ORDER BY wc.wc_id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Global Search ─────────────────────────────────────────────────

@bp.route("/api/search")
def global_search():
    from db import get_db
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": {}})
    if len(q) > 200:
        return jsonify({"error": "Query too long"}), 400
    db = get_db()
    like = f"%{q}%"
    results = {}
    results["work_orders"] = [dict(r) for r in db.execute(
        "SELECT wo_id, product_id, status, due_date FROM work_orders WHERE wo_id LIKE ? OR product_id LIKE ? LIMIT 5",
        (like, like)).fetchall()]
    results["products"] = [dict(r) for r in db.execute(
        "SELECT product_id, name, family FROM products WHERE product_id LIKE ? OR name LIKE ? LIMIT 5",
        (like, like)).fetchall()]
    results["equipment"] = [dict(r) for r in db.execute(
        "SELECT equipment_code, description, work_center_id FROM equipment WHERE equipment_code LIKE ? OR description LIKE ? LIMIT 5",
        (like, like)).fetchall()]
    results["personnel"] = [dict(r) for r in db.execute(
        "SELECT employee_code, employee_name, role FROM personnel WHERE employee_name LIKE ? OR employee_code LIKE ? LIMIT 5",
        (like, like)).fetchall()]
    results["lots"] = [dict(r) for r in db.execute(
        "SELECT DISTINCT output_lot, wo_id FROM lot_tracking WHERE output_lot LIKE ? LIMIT 5",
        (like,)).fetchall()]
    total = sum(len(v) for v in results.values())
    return jsonify({"query": q, "total": total, "results": results})
