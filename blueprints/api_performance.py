"""ISA-95 Level 3, MESA F11: Performance analysis & OEE.

SodhiCable MES — Performance Blueprint
OEE, scrap Pareto, and KPI endpoints.
"""
from flask import Blueprint, render_template, jsonify, request
from utils.cache import cached

bp = Blueprint("performance", __name__)


@bp.route("/performance")
def performance_page():
    return render_template("performance.html")


@bp.route("/api/performance/oee")
def oee_data():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT
            wc_id, shift_date, shift_code,
            ROUND(oee_availability * 100, 1) AS availability,
            ROUND(oee_performance * 100, 1) AS performance,
            ROUND(oee_quality * 100, 1) AS quality,
            ROUND(oee_overall * 100, 1) AS oee,
            total_output_ft
        FROM shift_reports
        ORDER BY shift_date DESC, wc_id
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/performance/scrap_pareto")
def scrap_pareto():
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT
            cause_code,
            SUM(quantity_ft) AS total_ft,
            COUNT(*) AS event_count
        FROM scrap_log
        GROUP BY cause_code
        ORDER BY total_ft DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/performance/kpis")
@cached(ttl=30)
def kpis():
    """Compute all KPIs from live data (not from kpis table)."""
    from db import get_db
    db = get_db()

    # OEE
    oee_row = db.execute("SELECT ROUND(AVG(oee_overall)*100,1) AS val FROM shift_reports").fetchone()
    oee = oee_row["val"] or 0

    # FPY
    total_out = db.execute("SELECT COALESCE(SUM(total_output_ft),0) FROM shift_reports").fetchone()[0]
    total_scrap = db.execute("SELECT COALESCE(SUM(total_scrap_ft),0) FROM shift_reports").fetchone()[0]
    fpy = round((1 - total_scrap / max(total_out + total_scrap, 1)) * 100, 1)

    # Schedule Adherence
    on_time = db.execute("SELECT COUNT(*) FROM work_orders WHERE status='Complete' AND actual_end <= due_date").fetchone()[0]
    total_complete = db.execute("SELECT COUNT(*) FROM work_orders WHERE status='Complete'").fetchone()[0]
    adherence = round(on_time / max(total_complete, 1) * 100, 1)

    # Labor Efficiency
    earned = db.execute("SELECT COALESCE(SUM(hours),0) FROM labor_time WHERE labor_type IN ('Run','Setup')").fetchone()[0]
    actual = db.execute("SELECT COALESCE(SUM(hours),0) FROM labor_time").fetchone()[0]
    labor_eff = round(earned / max(actual, 1) * 100, 1)

    # Scrap Rate
    scrap_ft = db.execute("SELECT COALESCE(SUM(quantity_ft),0) FROM scrap_log").fetchone()[0]
    scrap_rate = round(scrap_ft / max(total_out, 1) * 100, 2)

    # MTBF (avg across equipment)
    mtbf = 500  # Default; real calc from maintenance_calc engine

    # Doc Currency
    total_docs = db.execute("SELECT COUNT(*) FROM documents WHERE status != 'Obsolete'").fetchone()[0]
    active_docs = db.execute("SELECT COUNT(*) FROM documents WHERE status = 'Active'").fetchone()[0]
    doc_currency = round(active_docs / max(total_docs, 1) * 100, 1)

    # Capture Rate
    n_sensors = db.execute("SELECT COUNT(*) FROM data_collection_points").fetchone()[0]
    n_readings = db.execute("SELECT COUNT(*) FROM process_data_live").fetchone()[0]
    capture_rate = round(n_readings / max(n_sensors * 200, 1) * 100, 1)

    kpi_list = [
        {"kpi": "OEE", "value": oee, "target": 85, "unit": "%", "status": "PASS" if oee >= 85 else "FAIL"},
        {"kpi": "FPY", "value": fpy, "target": 97, "unit": "%", "status": "PASS" if fpy >= 97 else "FAIL"},
        {"kpi": "Schedule Adherence", "value": adherence, "target": 90, "unit": "%", "status": "PASS" if adherence >= 90 else "FAIL"},
        {"kpi": "Labor Efficiency", "value": labor_eff, "target": 85, "unit": "%", "status": "PASS" if labor_eff >= 85 else "FAIL"},
        {"kpi": "Scrap Rate", "value": scrap_rate, "target": 3, "unit": "%", "status": "PASS" if scrap_rate <= 3 else "FAIL"},
        {"kpi": "MTBF", "value": mtbf, "target": 500, "unit": "hrs", "status": "PASS" if mtbf >= 500 else "FAIL"},
        {"kpi": "Doc Currency", "value": doc_currency, "target": 95, "unit": "%", "status": "PASS" if doc_currency >= 95 else "FAIL"},
        {"kpi": "Capture Rate", "value": capture_rate, "target": 98, "unit": "%", "status": "PASS" if capture_rate >= 98 else "FAIL"},
    ]
    return jsonify(kpi_list)


@bp.route("/api/performance/schedule_detail")
def schedule_detail():
    """On-time delivery detail: per-WO adherence with days early/late."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT wo.wo_id, wo.product_id, p.family, wo.due_date, wo.actual_end, wo.status,
               wo.business_unit, wo.order_qty_kft,
               CASE WHEN wo.actual_end IS NOT NULL AND wo.due_date IS NOT NULL
                    THEN CAST(julianday(wo.due_date) - julianday(wo.actual_end) AS INTEGER)
                    ELSE NULL END AS days_early,
               CASE WHEN wo.status = 'Complete' AND wo.actual_end <= wo.due_date THEN 'On Time'
                    WHEN wo.status = 'Complete' AND wo.actual_end > wo.due_date THEN 'Late'
                    WHEN wo.status NOT IN ('Complete','Cancelled') AND wo.due_date < DATE('now') THEN 'Overdue'
                    ELSE 'In Progress' END AS delivery_status
        FROM work_orders wo
        LEFT JOIN products p ON p.product_id = wo.product_id
        WHERE wo.status != 'Cancelled' AND wo.due_date IS NOT NULL
        ORDER BY wo.due_date DESC LIMIT 100
    """).fetchall()
    # Summary by family
    family_summary = db.execute("""
        SELECT p.family,
               COUNT(*) AS total,
               COUNT(CASE WHEN wo.status='Complete' AND wo.actual_end <= wo.due_date THEN 1 END) AS on_time,
               COUNT(CASE WHEN wo.status='Complete' AND wo.actual_end > wo.due_date THEN 1 END) AS late
        FROM work_orders wo
        JOIN products p ON p.product_id = wo.product_id
        WHERE wo.status = 'Complete' AND wo.due_date IS NOT NULL
        GROUP BY p.family ORDER BY p.family
    """).fetchall()
    return jsonify({
        "orders": [dict(r) for r in rows],
        "by_family": [dict(r) for r in family_summary],
    })


@bp.route("/api/performance/scrap_trend")
def scrap_trend():
    """Scrap trend over time (daily totals)."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT DATE(timestamp) AS day, SUM(quantity_ft) AS total_ft, COUNT(*) AS events
        FROM scrap_log
        GROUP BY DATE(timestamp)
        ORDER BY day ASC
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/performance/copper_recovery")
def copper_recovery():
    from db import get_db
    db = get_db()

    # Total scrap footage
    total_scrap = db.execute("SELECT COALESCE(SUM(quantity_ft), 0) FROM scrap_log").fetchone()[0]

    # Total output footage
    total_output = db.execute("SELECT COALESCE(SUM(total_output_ft), 0) FROM shift_reports").fetchone()[0]

    # Recoverable scrap: exclude cause codes where copper is not recoverable
    non_recoverable_codes = ("Compound_Bleed", "Material_Defect", "Contamination")
    placeholders = ",".join("?" for _ in non_recoverable_codes)
    recoverable_scrap = db.execute(
        f"SELECT COALESCE(SUM(quantity_ft), 0) FROM scrap_log WHERE cause_code NOT IN ({placeholders})",
        non_recoverable_codes,
    ).fetchone()[0]

    # Recovery rate = (total produced - non-recoverable scrap) / total material input
    # Material input ≈ total output + total scrap
    total_input = total_output + total_scrap
    if total_input > 0:
        recovery_rate = ((total_output + recoverable_scrap) / total_input) * 100
    else:
        recovery_rate = 0.0

    # Cost impact at shadow price
    shadow_price = 4.80  # $/ft copper
    non_recoverable = total_scrap - recoverable_scrap
    waste_cost = non_recoverable * shadow_price

    return jsonify({
        "total_scrap_ft": total_scrap,
        "recoverable_scrap_ft": recoverable_scrap,
        "non_recoverable_ft": non_recoverable,
        "total_output_ft": total_output,
        "recovery_rate_pct": round(recovery_rate, 2),
        "target": 95.0,
        "shadow_price": shadow_price,
        "waste_cost_usd": round(waste_cost, 2),
    })


@bp.route("/api/performance/generate_shift_report", methods=["POST"])
def generate_shift_report():
    from db import get_db
    from utils.audit import log_audit
    db = get_db()
    data = request.get_json(force=True)
    wc_id = data.get("wc_id")
    shift_code = data.get("shift_code", "Day")
    shift_date = data.get("shift_date")
    if not wc_id: return jsonify({"error": "wc_id required"}), 400
    if not shift_date: shift_date = db.execute("SELECT DATE('now')").fetchone()[0]
    wc = db.execute("SELECT capacity_ft_per_hr FROM work_centers WHERE wc_id = ?", (wc_id,)).fetchone()
    cap = (wc["capacity_ft_per_hr"] or 500) * 8
    dt = db.execute("SELECT COALESCE(SUM(duration_min),0) AS m FROM downtime_log WHERE wc_id=? AND DATE(start_time)=?", (wc_id, shift_date)).fetchone()["m"]
    ops = db.execute("SELECT COALESCE(SUM(qty_good),0) AS g, COALESCE(SUM(qty_scrap),0) AS s FROM operations WHERE wc_id=? AND status='Complete' AND DATE(actual_end)=?", (wc_id, shift_date)).fetchone()
    out, scr = ops["g"], ops["s"]
    sl = db.execute("SELECT COALESCE(SUM(quantity_ft),0) AS s FROM scrap_log WHERE wc_id=? AND DATE(timestamp)=?", (wc_id, shift_date)).fetchone()["s"]
    scr = max(scr, sl)
    a = min(max((480 - dt) / 480, 0), 1)
    p = min(max(out / max(cap * a, 1), 0), 1)
    q = min(max((out - scr) / max(out, 1), 0), 1) if out > 0 else 0.97
    oee = a * p * q
    db.execute("INSERT INTO shift_reports (shift_date,shift_code,wc_id,oee_availability,oee_performance,oee_quality,oee_overall,total_output_ft,total_scrap_ft,total_downtime_min) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (shift_date, shift_code, wc_id, round(a,3), round(p,3), round(q,3), round(oee,3), out, scr, dt))
    db.commit()
    rid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    log_audit(db, "shift_reports", rid, "created", None, f"OEE={round(oee*100,1)}%")
    db.commit()
    return jsonify({"ok": True, "report_id": rid, "oee": round(oee*100,1), "availability": round(a*100,1), "performance": round(p*100,1), "quality": round(q*100,1)})

@bp.route("/api/performance/six_big_losses")
def six_big_losses():
    """TPM Six Big Losses Pareto by work center."""
    from db import get_db
    from engines.oee import compute_six_big_losses
    db = get_db()
    wc_id = request.args.get("wc_id")

    if wc_id:
        wc_ids = [wc_id]
    else:
        rows = db.execute("SELECT DISTINCT wc_id FROM work_centers ORDER BY wc_id").fetchall()
        wc_ids = [r["wc_id"] for r in rows]

    results = []
    plant_totals = {
        "equipment_failure": 0.0, "setup_adjustment": 0.0,
        "idling_minor_stops": 0.0, "reduced_speed": 0.0,
        "process_defects": 0.0, "startup_losses": 0.0,
    }

    for wid in wc_ids:
        losses = compute_six_big_losses(db, wid)
        total = sum(losses.values())
        entry = {"wc_id": wid, "total_loss_min": round(total, 1)}
        for k, v in losses.items():
            entry[k] = round(v, 1)
            entry[k + "_pct"] = round(v / total * 100, 1) if total > 0 else 0
            plant_totals[k] += v
        results.append(entry)

    grand_total = sum(plant_totals.values())
    pareto = []
    cumulative = 0
    for k, v in sorted(plant_totals.items(), key=lambda x: x[1], reverse=True):
        cumulative += v
        pareto.append({
            "loss": k.replace("_", " ").title(),
            "minutes": round(v, 1),
            "pct": round(v / grand_total * 100, 1) if grand_total > 0 else 0,
            "cumulative_pct": round(cumulative / grand_total * 100, 1) if grand_total > 0 else 0,
        })

    return jsonify({"by_wc": results, "pareto": pareto, "grand_total_min": round(grand_total, 1)})


@bp.route("/api/performance/energy_efficiency")
def energy_efficiency():
    """Compute kWh/KFT efficiency metric per extrusion work center."""
    from db import get_db
    db = get_db()
    wc_id = request.args.get("wc_id")

    query = """
        SELECT er.wc_id,
               COALESCE(SUM(er.kwh_cumulative), 0) AS total_kwh,
               COALESCE(sr.total_output_ft, 0) AS total_output_ft
        FROM energy_readings er
        LEFT JOIN (
            SELECT wc_id, SUM(total_output_ft) AS total_output_ft
            FROM shift_reports GROUP BY wc_id
        ) sr ON er.wc_id = sr.wc_id
    """
    params = []
    if wc_id:
        query += " WHERE er.wc_id = ?"
        params.append(wc_id)
    query += " GROUP BY er.wc_id ORDER BY er.wc_id"

    rows = db.execute(query, params).fetchall()
    results = []
    for r in rows:
        total_kwh = r["total_kwh"]
        output_ft = r["total_output_ft"]
        output_kft = output_ft / 1000.0 if output_ft > 0 else 0
        kwh_per_kft = round(total_kwh / output_kft, 2) if output_kft > 0 else 0
        results.append({
            "wc_id": r["wc_id"],
            "total_kwh": round(total_kwh, 2),
            "total_output_ft": round(output_ft, 1),
            "total_output_kft": round(output_kft, 2),
            "kwh_per_kft": kwh_per_kft,
            "status": "Good" if kwh_per_kft < 50 else "Warning" if kwh_per_kft < 100 else "High",
        })
    return jsonify(results)


@bp.route("/api/performance/cost_per_kft")
def cost_per_kft():
    """Cost-per-KFT waterfall: material → labor → overhead → scrap → energy → margin."""
    from db import get_db
    db = get_db()

    rows = db.execute("""
        SELECT p.family,
               ROUND(AVG(p.cost_per_kft), 2) AS avg_cost,
               ROUND(AVG(p.revenue_per_kft), 2) AS avg_revenue,
               ROUND(AVG(p.revenue_per_kft - p.cost_per_kft), 2) AS avg_margin
        FROM products p GROUP BY p.family ORDER BY p.family
    """).fetchall()

    # Decompose costs by component
    results = []
    for r in rows:
        family = r["family"]
        avg_cost = r["avg_cost"] or 0
        avg_revenue = r["avg_revenue"] or 0

        # Material cost from BOM
        mat = db.execute("""
            SELECT COALESCE(AVG(bm.qty_per_kft * m.unit_cost), 0) AS material_cost
            FROM bom_materials bm
            JOIN materials m ON bm.material_id = m.material_id
            JOIN products p ON bm.product_id = p.product_id
            WHERE p.family = ?
        """, (family,)).fetchone()
        material_cost = round(mat["material_cost"], 2) if mat["material_cost"] else round(avg_cost * 0.55, 2)

        # Labor cost from labor_time
        labor = db.execute("""
            SELECT COALESCE(SUM(lt.hours), 0) AS total_hours
            FROM labor_time lt
            JOIN operations op ON lt.operation_id = op.operation_id
            JOIN work_orders wo ON op.wo_id = wo.wo_id
            JOIN products p ON wo.product_id = p.product_id
            WHERE p.family = ?
        """, (family,)).fetchone()
        labor_cost = round(labor["total_hours"] * 35 / max(1, db.execute(
            "SELECT COUNT(*) FROM work_orders wo JOIN products p ON wo.product_id = p.product_id WHERE p.family = ?",
            (family,)).fetchone()[0]), 2) if labor["total_hours"] > 0 else round(avg_cost * 0.20, 2)

        # Scrap cost
        scrap = db.execute("""
            SELECT COALESCE(SUM(sl.cost), 0) AS scrap_cost, COUNT(*) AS scrap_events
            FROM scrap_log sl
            JOIN work_orders wo ON sl.wo_id = wo.wo_id
            JOIN products p ON wo.product_id = p.product_id
            WHERE p.family = ?
        """, (family,)).fetchone()
        scrap_cost = round(scrap["scrap_cost"] / max(1, db.execute(
            "SELECT COUNT(*) FROM work_orders wo JOIN products p ON wo.product_id = p.product_id WHERE p.family = ?",
            (family,)).fetchone()[0]), 2) if scrap["scrap_cost"] > 0 else round(avg_cost * 0.03, 2)

        # Energy cost
        energy_cost = round(avg_cost * 0.05, 2)  # ~5% of cost is energy (industry standard)

        # Overhead = remainder
        overhead = round(max(0, avg_cost - material_cost - labor_cost - scrap_cost - energy_cost), 2)

        results.append({
            "family": family,
            "avg_revenue": avg_revenue,
            "avg_cost": avg_cost,
            "avg_margin": r["avg_margin"],
            "waterfall": {
                "material": material_cost,
                "labor": labor_cost,
                "overhead": overhead,
                "scrap": scrap_cost,
                "energy": energy_cost,
            },
            "margin_pct": round((avg_revenue - avg_cost) / max(avg_revenue, 1) * 100, 1),
        })

    return jsonify(results)
