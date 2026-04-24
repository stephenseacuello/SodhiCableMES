"""ISA-95 Level 4: Supplier management.

SodhiCable MES — Supplier Performance Scorecards Blueprint
Item #12: Supplier scorecard metrics and drill-down by supplier.
"""
from flask import Blueprint, render_template, jsonify, request, redirect

bp = Blueprint("suppliers", __name__)


@bp.route("/suppliers")
def suppliers_page():
    return redirect("/erp?tab=procurement")


@bp.route("/api/suppliers/scorecard")
def supplier_scorecard():
    """Aggregate scorecard for every supplier: materials count, avg lead time,
    total on-hand inventory, and availability percentage."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT m.supplier,
               COUNT(DISTINCT m.material_id) AS materials_supplied,
               ROUND(AVG(m.lead_time_days), 1) AS avg_lead_time,
               COALESCE(SUM(i.qty_on_hand), 0) AS total_on_hand,
               ROUND(AVG(CASE WHEN i.status = 'Available' THEN 1.0 ELSE 0.0 END) * 100, 1) AS availability_pct
        FROM materials m
        LEFT JOIN inventory i ON i.material_id = m.material_id
        WHERE m.supplier IS NOT NULL
        GROUP BY m.supplier
        ORDER BY m.supplier
    """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/suppliers/materials")
def supplier_materials():
    """Return all materials for a given supplier with aggregated on-hand qty."""
    from db import get_db
    db = get_db()
    supplier = request.args.get("supplier", "")
    if not supplier:
        return jsonify([])
    rows = db.execute("""
        SELECT m.*, COALESCE(SUM(i.qty_on_hand), 0) AS total_on_hand
        FROM materials m
        LEFT JOIN inventory i ON i.material_id = m.material_id
        WHERE m.supplier = ?
        GROUP BY m.material_id
        ORDER BY m.material_id
    """, (supplier,)).fetchall()
    return jsonify([dict(r) for r in rows])
