"""ISA-95 Level 4: Executive KPIs & financial reporting.

SodhiCable MES — Executive Blueprint
Single aggregated endpoint returning all KPIs the executive dashboard needs.
"""
from flask import Blueprint, render_template, jsonify, request

bp = Blueprint("executive", __name__)


def _exec_filter(date_col="shift_date", wc_col="wc_id", family_col="", shift_col=""):
    """Build WHERE clauses from ?date_from=&date_to=&wc_id=&family=&shift= query params."""
    clauses, params = [], []
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    wc_id = request.args.get("wc_id", "")
    family = request.args.get("family", "")
    shift = request.args.get("shift", "")
    # Strip time from datetime-local inputs so DATE comparisons work correctly
    if date_from and "T" in date_from:
        date_from = date_from.split("T")[0]
    if date_to and "T" in date_to:
        date_to = date_to.split("T")[0]
    if date_from:
        clauses.append(f"{date_col} >= ?"); params.append(date_from)
    if date_to:
        clauses.append(f"{date_col} <= ?"); params.append(date_to)
    if wc_id:
        clauses.append(f"{wc_col} = ?"); params.append(wc_id)
    if family and family_col:
        clauses.append(f"{family_col} = ?"); params.append(family)
    if shift and shift_col:
        clauses.append(f"{shift_col} = ?"); params.append(shift)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


@bp.route("/executive")
def executive_page():
    return render_template("executive.html")


@bp.route("/api/executive/summary")
def executive_summary():
    """Return everything the executive dashboard needs in one call.
    Supports ?date_from=&date_to=&wc_id= filters."""
    from db import get_db
    db = get_db()
    filt, fparams = _exec_filter(shift_col="shift_code")

    # ── 1. Plant OEE % ──────────────────────────────────────────────
    row = db.execute(
        f"SELECT ROUND(AVG(oee_overall) * 100, 1) AS plant_oee FROM shift_reports WHERE 1=1{filt}", fparams
    ).fetchone()
    plant_oee = row["plant_oee"] if row and row["plant_oee"] else 0

    # Previous-period OEE for trend arrow
    oee_halves = db.execute(f"""
        SELECT shift_date, oee_overall FROM shift_reports WHERE 1=1{filt} ORDER BY shift_date
    """, fparams).fetchall()
    prev_oee = 0
    if len(oee_halves) > 4:
        mid = len(oee_halves) // 2
        prev_oee = round(
            sum(r["oee_overall"] for r in oee_halves[:mid]) / mid * 100, 1
        )

    # ── 2. On-Time Delivery % (Schedule Adherence) ──────────────────
    family = request.args.get("family", "")
    product_id = request.args.get("product_id", "")
    wo_clauses, wo_params = [], []
    df = request.args.get("date_from", "")
    dt = request.args.get("date_to", "")
    # Normalize datetime-local to date-only for consistent comparison
    if df and "T" in df: df = df.split("T")[0]
    if dt and "T" in dt: dt = dt.split("T")[0]
    if df: wo_clauses.append("DATE(wo.actual_end) >= ?"); wo_params.append(df)
    if dt: wo_clauses.append("DATE(wo.actual_end) <= ?"); wo_params.append(dt)
    if family: wo_clauses.append("p.family = ?"); wo_params.append(family)
    if product_id: wo_clauses.append("p.product_id = ?"); wo_params.append(product_id)
    wo_where = (" AND " + " AND ".join(wo_clauses)) if wo_clauses else ""
    ot_row = db.execute(f"""
        SELECT
            COUNT(CASE WHEN wo.actual_end <= wo.due_date THEN 1 END) AS on_time,
            COUNT(*) AS total
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        WHERE wo.status = 'Complete' AND wo.due_date IS NOT NULL AND wo.actual_end IS NOT NULL{wo_where}
    """, wo_params).fetchone()
    on_time_count = ot_row["on_time"] if ot_row else 0
    total_complete = ot_row["total"] if ot_row else 0
    on_time_pct = round(on_time_count / max(total_complete, 1) * 100, 1)
    late_count = total_complete - on_time_count

    # ── 3. Cost per KFT — computed from actual WO data when filtered ─
    prod_clauses, prod_params = [], []
    if family: prod_clauses.append("p.family = ?"); prod_params.append(family)
    if product_id: prod_clauses.append("p.product_id = ?"); prod_params.append(product_id)
    fam_where = (" WHERE " + " AND ".join(prod_clauses)) if prod_clauses else ""
    fam_params = prod_params

    # If date or WC filter active, compute cost from actual WO data
    wc_id = request.args.get("wc_id", "")
    shift = request.args.get("shift", "")
    if df or dt or wc_id:
        cost_clauses = list(prod_clauses)
        cost_params = list(prod_params)
        if df: cost_clauses.append("wo.actual_end >= ?"); cost_params.append(df)
        if dt: cost_clauses.append("wo.actual_end <= ?"); cost_params.append(dt)
        cost_where = (" AND " + " AND ".join(cost_clauses)) if cost_clauses else ""
        cost_row = db.execute(f"""
            SELECT ROUND(AVG(p.cost_per_kft), 2) AS avg_cost
            FROM work_orders wo JOIN products p ON wo.product_id = p.product_id
            WHERE wo.status = 'Complete'{cost_where}
        """, cost_params).fetchone()
    else:
        cost_row = db.execute(f"""
            SELECT ROUND(AVG(p.cost_per_kft), 2) AS avg_cost FROM products p{fam_where}
        """, fam_params).fetchone()
    cost_per_kft = cost_row["avg_cost"] if cost_row and cost_row["avg_cost"] else 0

    # Cost breakdown by family (for waterfall chart)
    cost_by_family = db.execute(f"""
        SELECT p.family,
               ROUND(AVG(p.cost_per_kft), 2) AS avg_cost,
               ROUND(AVG(p.revenue_per_kft), 2) AS avg_revenue,
               ROUND(AVG(p.revenue_per_kft - p.cost_per_kft), 2) AS avg_margin
        FROM products p{fam_where}
        GROUP BY p.family ORDER BY p.family
    """, fam_params).fetchall()
    cost_families = [dict(r) for r in cost_by_family]

    # ── 4. Scrap $ (filter by date, WC, family, product) ────────────
    scrap_clauses, scrap_params = [], []
    if df: scrap_clauses.append("sl.timestamp >= ?"); scrap_params.append(df)
    if dt: scrap_clauses.append("sl.timestamp <= ?"); scrap_params.append(dt)
    if wc_id: scrap_clauses.append("sl.wc_id = ?"); scrap_params.append(wc_id)
    if family or product_id:
        scrap_join = " LEFT JOIN work_orders wo ON sl.wo_id=wo.wo_id LEFT JOIN products p ON wo.product_id=p.product_id"
        if family: scrap_clauses.append("p.family = ?"); scrap_params.append(family)
        if product_id: scrap_clauses.append("p.product_id = ?"); scrap_params.append(product_id)
    else:
        scrap_join = ""
    scrap_where = (" AND " + " AND ".join(scrap_clauses)) if scrap_clauses else ""
    scrap_row = db.execute(f"""
        SELECT COALESCE(SUM(sl.quantity_ft), 0) AS total_scrap_ft,
               COALESCE(SUM(sl.cost), 0) AS total_scrap_cost
        FROM scrap_log sl{scrap_join} WHERE 1=1{scrap_where}
    """, scrap_params).fetchone()
    total_scrap_ft = scrap_row["total_scrap_ft"]
    total_scrap_cost = scrap_row["total_scrap_cost"]

    # If scrap_log.cost is mostly NULL, estimate from avg product cost
    if total_scrap_cost == 0 and total_scrap_ft > 0:
        avg_cost_row = db.execute(
            "SELECT AVG(cost_per_kft) AS ac FROM products"
        ).fetchone()
        avg_c = avg_cost_row["ac"] if avg_cost_row and avg_cost_row["ac"] else 0
        # cost_per_kft is per 1000 ft, so per-ft = cost_per_kft / 1000
        total_scrap_cost = round(total_scrap_ft * avg_c / 1000, 2)

    # ── 5. OEE Trend (last 14 days) ─────────────────────────────────
    oee_trend = db.execute(f"""
        SELECT shift_date,
               ROUND(AVG(oee_overall) * 100, 1) AS avg_oee
        FROM shift_reports WHERE 1=1{filt}
        GROUP BY shift_date
        ORDER BY shift_date DESC
        LIMIT 14
    """, fparams).fetchall()
    oee_trend_data = [dict(r) for r in reversed(oee_trend)]

    # ── 6. On-Time vs Late work orders (for donut chart) ────────────
    # Already computed: on_time_count, late_count

    # ── 7. Top 5 Issues (filtered by WC when active) ─────────────────
    issues = []
    import statistics

    # Build WC clause for issues queries
    issue_wc_clause = " AND wc_id = ?" if wc_id else ""
    issue_wc_params = [wc_id] if wc_id else []
    issue_ewc_clause = " AND e.work_center_id = ?" if wc_id else ""

    # 7a. Low Cpk work centers (Cpk < 1.33)
    cpk_rows = db.execute(f"""
        SELECT wc_id, parameter_name,
               AVG(measured_value) AS mean_val,
               COUNT(*) AS n, usl, lsl
        FROM spc_readings
        WHERE measured_value IS NOT NULL AND usl IS NOT NULL AND lsl IS NOT NULL{issue_wc_clause}
        GROUP BY wc_id, parameter_name
        HAVING COUNT(*) >= 5
    """, issue_wc_params).fetchall()
    for r in cpk_rows:
        vals = db.execute(
            "SELECT measured_value FROM spc_readings WHERE wc_id=? AND parameter_name=? AND measured_value IS NOT NULL",
            (r["wc_id"], r["parameter_name"])
        ).fetchall()
        if len(vals) < 2:
            continue
        sigma = statistics.stdev([v["measured_value"] for v in vals])
        if sigma > 0 and r["usl"] and r["lsl"]:
            mean = r["mean_val"]
            cpk = min((r["usl"] - mean) / (3 * sigma), (mean - r["lsl"]) / (3 * sigma))
            if cpk < 1.33:
                issues.append({
                    "type": "Low Cpk",
                    "detail": f"{r['wc_id']} / {r['parameter_name']} — Cpk {cpk:.2f}",
                    "severity": "red" if cpk < 1.0 else "yellow"
                })

    # 7b. Overdue PMs
    overdue_pms = db.execute(f"""
        SELECT e.equipment_code, e.work_center_id, ms.next_due
        FROM maintenance_schedule ms
        JOIN equipment e ON e.equipment_id = ms.equipment_id
        WHERE ms.next_due < date('now'){issue_ewc_clause}
        ORDER BY ms.next_due ASC LIMIT 5
    """, issue_wc_params).fetchall()
    for pm in overdue_pms:
        issues.append({
            "type": "Overdue PM",
            "detail": f"{pm['equipment_code']} ({pm['work_center_id']}) — due {pm['next_due']}",
            "severity": "red"
        })

    # 7c. Active NCRs (filter by WC via detected_at)
    ncr_wc_clause = " AND detected_at = ?" if wc_id else ""
    active_ncrs = db.execute(f"""
        SELECT ncr_id, severity, defect_type, wo_id, detected_at
        FROM ncr WHERE status = 'Open'{ncr_wc_clause}
        ORDER BY reported_date DESC LIMIT 5
    """, issue_wc_params).fetchall()
    for ncr in active_ncrs:
        issues.append({
            "type": "Open NCR",
            "detail": f"NCR-{ncr['ncr_id']} ({ncr['severity']}) — {ncr['defect_type'] or 'N/A'} on {ncr['wo_id'] or '?'}",
            "severity": "red" if ncr["severity"] == "Major" else "yellow"
        })

    # 7d. Critical alarms (process deviations unresolved)
    alarms = db.execute(f"""
        SELECT wc_id, parameter_name, severity
        FROM process_deviations
        WHERE resolved = 0 AND severity IN ('Critical', 'Warning'){issue_wc_clause}
        ORDER BY timestamp DESC LIMIT 5
    """, issue_wc_params).fetchall()
    for a in alarms:
        issues.append({
            "type": "Alarm",
            "detail": f"{a['wc_id']} — {a['parameter_name']} ({a['severity']})",
            "severity": "red" if a["severity"] == "Critical" else "yellow"
        })

    # Sort issues: red first, then yellow, take top 5
    severity_order = {"red": 0, "yellow": 1}
    issues.sort(key=lambda x: severity_order.get(x["severity"], 2))
    top_issues = issues[:5]

    # ── 8. Revenue & Margin ───────────────────────────────────────────
    rev_row = db.execute(f"""
        SELECT ROUND(AVG(p.revenue_per_kft), 2) AS avg_revenue,
               ROUND(AVG(p.revenue_per_kft - p.cost_per_kft), 2) AS avg_margin
        FROM products p{fam_where}
    """, fam_params).fetchone()
    avg_revenue = rev_row["avg_revenue"] if rev_row and rev_row["avg_revenue"] else 0
    avg_margin = rev_row["avg_margin"] if rev_row and rev_row["avg_margin"] else 0
    margin_pct = round(avg_margin / max(avg_revenue, 0.01) * 100, 1) if avg_revenue > 0 else 0

    # ── 9. On-Time by Business Unit ────────────────────────────────
    bu_rows = db.execute(f"""
        SELECT c.business_unit,
               COUNT(*) AS total,
               COUNT(CASE WHEN wo.actual_end <= wo.due_date THEN 1 END) AS on_time
        FROM work_orders wo
        JOIN products p ON wo.product_id = p.product_id
        LEFT JOIN sales_orders so ON wo.sales_order_id = so.sales_order_id
        LEFT JOIN customers c ON so.customer_id = c.customer_id
        WHERE wo.status = 'Complete' AND wo.due_date IS NOT NULL{wo_where}
        GROUP BY c.business_unit
        ORDER BY total DESC
    """, wo_params).fetchall()
    by_business_unit = []
    for r in bu_rows:
        bu = r["business_unit"] or "Unassigned"
        tot = r["total"] or 0
        ot = r["on_time"] or 0
        by_business_unit.append({
            "business_unit": bu, "total": tot, "on_time": ot,
            "on_time_pct": round(ot / max(tot, 1) * 100, 1),
            "late": tot - ot,
        })

    # ── 10. Period-over-Period Comparison ───────────────────────────
    # Compare current period vs previous equal-length period
    if df and dt:
        from datetime import datetime as _dt, timedelta
        try:
            d1 = _dt.fromisoformat(df.replace("T", " ").split(".")[0])
            d2 = _dt.fromisoformat(dt.replace("T", " ").split(".")[0])
            span = d2 - d1
            prev_from = (d1 - span).isoformat()
            prev_to = d1.isoformat()
        except Exception:
            prev_from, prev_to = None, None
    else:
        prev_from, prev_to = None, None

    if prev_from:
        prev_filt = f" AND shift_date >= ? AND shift_date <= ?"
        prev_p = [prev_from, prev_to]
        if wc_id: prev_filt += " AND wc_id = ?"; prev_p.append(wc_id)
        if shift: prev_filt += " AND shift_code = ?"; prev_p.append(shift)
        prev_oee_row = db.execute(f"SELECT ROUND(AVG(oee_overall)*100,1) AS v FROM shift_reports WHERE 1=1{prev_filt}", prev_p).fetchone()
        prev_scrap_row = db.execute(f"SELECT COALESCE(SUM(quantity_ft),0) AS v FROM scrap_log WHERE timestamp >= ? AND timestamp <= ?", [prev_from, prev_to]).fetchone()
        period_comparison = {
            "prev_period": f"{prev_from[:10]} to {prev_to[:10]}",
            "curr_period": f"{df[:10] if df else '?'} to {dt[:10] if dt else '?'}",
            "prev_oee": prev_oee_row["v"] if prev_oee_row and prev_oee_row["v"] else 0,
            "curr_oee": plant_oee,
            "oee_delta": round(plant_oee - (prev_oee_row["v"] or 0), 1),
            "prev_scrap_ft": prev_scrap_row["v"] if prev_scrap_row else 0,
            "curr_scrap_ft": total_scrap_ft,
            "scrap_delta_ft": round(total_scrap_ft - (prev_scrap_row["v"] or 0), 1),
        }
    else:
        period_comparison = None

    # ── 11. Material Risk Summary ──────────────────────────────────
    mat_risk = db.execute("""
        SELECT m.material_id, m.name,
               i.qty_on_hand, i.qty_allocated,
               (i.qty_on_hand - i.qty_allocated) AS available,
               m.lead_time_days,
               COALESCE(b.min_level, 10) AS safety_stock,
               CASE WHEN (i.qty_on_hand - i.qty_allocated) <= 0 THEN 'STOCKOUT'
                    WHEN (i.qty_on_hand - i.qty_allocated) < COALESCE(b.min_level, 10) THEN 'BELOW SAFETY'
                    ELSE 'OK' END AS status
        FROM inventory i
        JOIN materials m ON i.material_id = m.material_id
        LEFT JOIN buffer_inventory b ON i.material_id = b.material_id
        WHERE (i.qty_on_hand - i.qty_allocated) < COALESCE(b.min_level, 10) * 1.5
        ORDER BY (i.qty_on_hand - i.qty_allocated) ASC
        LIMIT 5
    """).fetchall()
    material_risks = [dict(r) for r in mat_risk]

    # ── 12. Energy Cost Summary (filtered by date and WC) ──────────
    energy_clauses, energy_params = [], []
    if df: energy_clauses.append("timestamp >= ?"); energy_params.append(df)
    if dt: energy_clauses.append("timestamp <= ?"); energy_params.append(dt)
    if wc_id: energy_clauses.append("wc_id = ?"); energy_params.append(wc_id)
    energy_where = (" WHERE " + " AND ".join(energy_clauses)) if energy_clauses else ""
    energy_row = db.execute(f"""
        SELECT ROUND(SUM(kwh_cumulative), 1) AS total_kwh,
               COUNT(DISTINCT wc_id) AS wc_count
        FROM energy_readings{energy_where}
    """, energy_params).fetchone()
    total_kwh = energy_row["total_kwh"] if energy_row and energy_row["total_kwh"] else 0
    energy_cost_per_kwh = 0.12  # $/kWh industry average
    total_energy_cost = round(total_kwh * energy_cost_per_kwh, 2)

    return jsonify({
        "plant_oee": plant_oee,
        "prev_oee": prev_oee,
        "on_time_pct": on_time_pct,
        "on_time_count": on_time_count,
        "late_count": late_count,
        "total_complete_wos": total_complete,
        "cost_per_kft": cost_per_kft,
        "cost_by_family": cost_families,
        "total_scrap_ft": total_scrap_ft,
        "total_scrap_cost": round(total_scrap_cost, 2),
        "oee_trend": oee_trend_data,
        "top_issues": top_issues,
        # New fields
        "avg_revenue_per_kft": avg_revenue,
        "avg_margin_per_kft": avg_margin,
        "margin_pct": margin_pct,
        "by_business_unit": by_business_unit,
        "period_comparison": period_comparison,
        "material_risks": material_risks,
        "total_energy_kwh": total_kwh,
        "total_energy_cost": total_energy_cost,
        "energy_cost_per_kwh": energy_cost_per_kwh,
    })
