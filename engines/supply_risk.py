"""
engines/supply_risk.py - Supply Chain Risk Engine

Computes inventory coverage days, flags single-source materials,
and builds a composite risk heat-map score for each raw material
in the SodhiCable MES.
"""


# ---------------------------------------------------------------------------
# Coverage days
# ---------------------------------------------------------------------------
def compute_coverage_days(conn):
    """Calculate how many days of production each material can sustain.

    Reads from: materials (columns: material_id, name, qty_on_hand,
    daily_usage).

    Parameters
    ----------
    conn : sqlite3.Connection

    Returns
    -------
    list[dict]
        Each entry: material_id, name, qty_on_hand, daily_usage,
        coverage_days, status ('OK' / 'LOW' / 'CRITICAL').

        Thresholds: CRITICAL < 3 days, LOW < 7 days, else OK.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT m.material_id, m.name, m.lead_time_days, m.safety_stock_qty, m.supplier,
               COALESCE(i.qty_on_hand, 0) AS qty_on_hand
        FROM materials m
        LEFT JOIN inventory i ON m.material_id = i.material_id
    """)
    rows = cur.fetchall()

    # Estimate daily usage from BOM demand and active work orders
    demand_cur = cur.execute("""
        SELECT bm.material_id, SUM(bm.qty_per_kft * wo.order_qty_kft) / 30.0 AS daily_usage
        FROM bom_materials bm
        JOIN work_orders wo ON wo.product_id = bm.product_id
        WHERE wo.status IN ('Pending', 'Released', 'InProcess')
        GROUP BY bm.material_id
    """)
    usage_map = {r[0]: r[1] for r in demand_cur.fetchall()}

    results = []
    for row in rows:
        material_id = row[0]
        name = row[1]
        qty = row[5] or 0
        usage = usage_map.get(material_id, 0)
        if usage and usage > 0:
            coverage = qty / usage
        else:
            coverage = float("inf")

        if coverage < 3:
            status = "CRITICAL"
        elif coverage < 7:
            status = "LOW"
        else:
            status = "OK"

        results.append({
            "material_id": material_id,
            "name": name,
            "qty_on_hand": qty,
            "daily_usage": round(usage, 2) if usage else 0,
            "coverage_days": round(coverage, 1) if coverage != float("inf") else 999,
            "lead_time_days": row[2] or 0,
            "safety_stock_qty": row[3] or 0,
            "supplier": row[4] or "Unknown",
            "status": status,
        })

    return results


# ---------------------------------------------------------------------------
# Single-source analysis
# ---------------------------------------------------------------------------
def single_source_analysis(conn):
    """Flag materials that have only one approved supplier.

    Reads from: material_suppliers (columns: material_id, supplier_id)
    and materials (columns: material_id, name).

    Parameters
    ----------
    conn : sqlite3.Connection

    Returns
    -------
    list[dict]
        Each entry: material_id, name, supplier_count, is_single_source.
        Only materials with supplier_count == 1 are flagged.
    """
    cur = conn.cursor()
    cur.execute(
        """SELECT m.material_id, m.name, COUNT(ms.supplier_id) AS cnt
           FROM materials m
           LEFT JOIN material_suppliers ms
             ON m.material_id = ms.material_id
           GROUP BY m.material_id, m.name"""
    )
    rows = cur.fetchall()

    results = []
    for material_id, name, cnt in rows:
        results.append({
            "material_id": material_id,
            "name": name,
            "supplier_count": cnt,
            "is_single_source": cnt <= 1,
        })

    return results


# ---------------------------------------------------------------------------
# Risk heat map
# ---------------------------------------------------------------------------
def risk_heat_map(conn):
    """Build a composite supply-risk score (0-100) for each material.

    Factors
    -------
    - coverage_score (40 %): lower coverage -> higher risk.
      Score = max(0, 40 - (coverage_days / 7) * 40)
    - single_source_score (30 %): 30 if single-source, else 0.
    - lead_time_score (30 %): longer lead time -> higher risk.
      Score = min(30, (lead_time_days / 30) * 30)

    Reads from: materials (columns: material_id, name, qty_on_hand,
    daily_usage, lead_time_days) and material_suppliers.

    Parameters
    ----------
    conn : sqlite3.Connection

    Returns
    -------
    list[dict]
        Each entry: material_id, risk_score (0-100), factors dict.
        Sorted by risk_score descending.
    """
    coverage = {r["material_id"]: r for r in compute_coverage_days(conn)}
    singles = {r["material_id"]: r for r in single_source_analysis(conn)}

    cur = conn.cursor()
    cur.execute("SELECT material_id, name, lead_time_days FROM materials")
    rows = cur.fetchall()

    results = []
    for material_id, name, lead_time_days in rows:
        # Coverage factor (0-40)
        cov_info = coverage.get(material_id, {})
        cov_days = cov_info.get("coverage_days")
        if cov_days is None or cov_days == float("inf"):
            coverage_score = 0.0
        else:
            coverage_score = max(0.0, 40.0 - (cov_days / 7.0) * 40.0)

        # Single-source factor (0 or 30)
        ss_info = singles.get(material_id, {})
        single_source_score = 30.0 if ss_info.get("is_single_source", False) else 0.0

        # Lead-time factor (0-30)
        lt = lead_time_days if lead_time_days else 0
        lead_time_score = min(30.0, (lt / 30.0) * 30.0)

        risk_score = coverage_score + single_source_score + lead_time_score

        results.append({
            "material_id": material_id,
            "name": name,
            "risk_score": round(risk_score, 1),
            "factors": {
                "coverage_score": round(coverage_score, 1),
                "single_source_score": round(single_source_score, 1),
                "lead_time_score": round(lead_time_score, 1),
            },
        })

    results.sort(key=lambda r: r["risk_score"], reverse=True)
    return results
