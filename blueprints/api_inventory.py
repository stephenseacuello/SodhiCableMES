"""ISA-95 Level 3, MESA F3: Material & inventory management.

SodhiCable MES — Inventory Blueprint
Material availability, buffer status, CSV export, and cable length calculator.
"""
import csv
import io

from flask import Blueprint, render_template, jsonify, request, Response, redirect

bp = Blueprint("inventory", __name__)


@bp.route("/inventory")
def inventory_page():
    return redirect("/erp?tab=inventory")


@bp.route("/api/inventory/availability")
def material_availability():
    from db import get_db
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM vw_material_availability").fetchall()
    except Exception:
        # View may not exist; fall back to materials table
        rows = db.execute("""
            SELECT material_id, description, unit, qty_on_hand, reorder_point, lead_time_days
            FROM materials
            ORDER BY material_id
        """).fetchall()
    return jsonify([dict(r) for r in rows])


@bp.route("/api/inventory/shelf_life")
def shelf_life():
    """Compound shelf-life countdown — shows hours remaining, auto-quarantines expired lots."""
    from db import get_db
    from datetime import datetime
    db = get_db()

    rows = db.execute("""
        SELECT i.inv_id, i.material_id, m.name AS material_name, m.material_type,
               i.lot_number, i.qty_on_hand, i.uom, i.expiration_date, i.fifo_date,
               i.status, i.location_code
        FROM inventory i
        JOIN materials m ON m.material_id = i.material_id
        WHERE i.expiration_date IS NOT NULL
        ORDER BY i.expiration_date ASC
    """).fetchall()

    now = datetime.now()
    results = []
    expired_count = 0
    critical_count = 0

    for r in rows:
        d = dict(r)
        try:
            exp = datetime.strptime(d["expiration_date"], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            try:
                exp = datetime.strptime(d["expiration_date"], "%Y-%m-%d")
            except:
                continue

        delta = exp - now
        hours_left = round(delta.total_seconds() / 3600, 1)

        if hours_left < 0:
            status = "EXPIRED"
            expired_count += 1
            # Auto-quarantine
            if d["status"] != "Quarantine":
                db.execute("UPDATE inventory SET status = 'Quarantine' WHERE inv_id = ?", (d["inv_id"],))
        elif hours_left < 6:
            status = "CRITICAL"
            critical_count += 1
        elif hours_left < 24:
            status = "WARNING"
        else:
            status = "OK"

        # Shelf life type
        is_reactive = any(x in d["material_name"] for x in ["FEP", "ETFE"])
        shelf_type = "Reactive (24-72 hrs)" if is_reactive else "Thermoplastic (7 days)"

        d["hours_remaining"] = hours_left
        d["shelf_status"] = status
        d["shelf_type"] = shelf_type
        d["mixed_date"] = d.get("fifo_date")
        results.append(d)

    db.commit()

    return jsonify({
        "compounds": results,
        "total": len(results),
        "expired": expired_count,
        "critical": critical_count,
        "quarantined": expired_count,
    })


@bp.route("/api/inventory/buffers")
def buffer_status():
    from db import get_db
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM vw_buffer_status").fetchall()
    except Exception:
        rows = []
    return jsonify([dict(r) for r in rows])


@bp.route("/api/inventory/export")
def inventory_export():
    """Export inventory data as CSV."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT i.inv_id, i.material_id, m.name AS material_name, i.product_id,
               i.location_code, i.lot_number, i.qty_on_hand, i.qty_allocated, i.uom,
               i.receipt_date, i.status
        FROM inventory i
        LEFT JOIN materials m ON i.material_id = m.material_id
        ORDER BY i.material_id
    """).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Material', 'Name', 'Product', 'Location', 'Lot',
                     'On Hand', 'Allocated', 'UOM', 'Receipt Date', 'Status'])
    for r in rows:
        writer.writerow([r['inv_id'], r['material_id'], r['material_name'], r['product_id'],
                        r['location_code'], r['lot_number'], r['qty_on_hand'], r['qty_allocated'],
                        r['uom'], r['receipt_date'], r['status']])
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=inventory_export.csv'})


@bp.route("/api/inventory/cable_length_calc", methods=["POST"])
def cable_length_calc():
    """Calculate remaining cable length on a drum by weight."""
    data = request.get_json(force=True)
    try:
        current_weight_lb = float(data.get("current_weight_lb", 0))
        tare_weight_lb = float(data.get("tare_weight_lb", 0))
        weight_per_kft = float(data.get("weight_per_kft", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "All weight values must be numbers"}), 400

    if weight_per_kft <= 0:
        return jsonify({"error": "weight_per_kft must be > 0"}), 400

    net_cable_weight = current_weight_lb - tare_weight_lb
    remaining_ft = (net_cable_weight / weight_per_kft) * 1000

    return jsonify({
        "net_cable_weight_lb": round(net_cable_weight, 2),
        "remaining_ft": round(max(0, remaining_ft), 1),
        "remaining_kft": round(max(0, remaining_ft / 1000), 3),
    })


@bp.route("/api/inventory/products_weight")
def products_weight():
    """Return products with weight data for cable length calculator dropdown."""
    from db import get_db
    db = get_db()
    rows = db.execute("""
        SELECT product_id, name, family, weight
        FROM products
        WHERE weight IS NOT NULL AND weight > 0
        ORDER BY family, name
    """).fetchall()
    return jsonify([dict(r) for r in rows])
