"""
SodhiCable MES — ERP Simulator (Level 4)

Background thread that simulates ERP business cycle activity:
- Demand generation (new sales orders, ~30% chance per tick)
- Order-to-Cash progression (SO -> WO -> Ship -> Invoice -> Paid, every tick)
- Procure-to-Pay (low stock -> PO -> Goods Receipt -> Inventory, every 3 ticks)
- Demand forecasting (SES per product family, every 5 ticks)
- Financial posting (Revenue/COGS on WO completion, every tick)
- ISA-95 message logging (L3<->L4 boundary)

Mirrors engines/opcua_sim.py pattern exactly.
Tick interval: 10 seconds (each tick ~= 1 simulated business day).
"""
import threading
import time
import random
import sqlite3
import math
from datetime import datetime, timedelta

_running = False
_thread = None
_tick = 0


def _log_isa95(conn, direction, msg_type, src, tgt, summary, ref_id):
    """Helper to insert an ISA-95 boundary message."""
    conn.execute(
        """INSERT INTO isa95_messages (direction, message_type, source_system, target_system,
           payload_summary, reference_id, status, processing_time_ms)
           VALUES (?,?,?,?,?,?,?,?)""",
        (direction, msg_type, src, tgt, summary, ref_id, "Processed", random.randint(10, 300)))


def _get_state(conn, key, default="0"):
    row = conn.execute("SELECT value FROM erp_sim_state WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _set_state(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO erp_sim_state (key, value, updated) VALUES (?, ?, datetime('now'))",
                 (key, str(value)))


def _run(db_path, interval):
    global _running, _tick
    _tick = 0
    while _running:
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row

            sim_week = int(_get_state(conn, "sim_week", "17"))
            total_orders = int(_get_state(conn, "total_orders_generated", "15"))
            total_pos = int(_get_state(conn, "total_pos_created", "15"))

            # ── 1. Demand Generation (every 3 ticks, 50% chance — ~1 order) ──
            if _tick % 3 == 0 and random.random() < 0.5:
                customers = [r[0] for r in conn.execute("SELECT customer_id FROM customers").fetchall()]
                products = conn.execute("SELECT product_id, family, revenue_per_kft FROM products").fetchall()
                if customers and products:
                    total_orders += 1
                    so_id = f"SO-ERP-{total_orders:04d}"
                    cust = random.choice(customers)
                    prod = random.choice(products)
                    seasonal = 1 + 0.25 * math.sin(2 * math.pi * sim_week / 52)
                    qty = round(random.uniform(1, 8) * seasonal, 1)
                    due_days = random.randint(7, 28)
                    bus_units = ["Defense", "Industrial", "Infrastructure", "Oil & Gas"]

                    conn.execute(
                        """INSERT OR IGNORE INTO sales_orders
                           (sales_order_id, customer_id, order_date, required_date, priority, status, business_unit)
                           VALUES (?,?,datetime('now'),date('now',?),?,?,?)""",
                        (so_id, cust, f"+{due_days} days", random.randint(1, 5), "Open",
                         random.choice(bus_units)))
                    conn.execute(
                        "INSERT INTO sales_order_lines (sales_order_id, product_id, quantity, unit_price, promised_date) VALUES (?,?,?,?,date('now',?))",
                        (so_id, prod[0], qty, prod[2] or 50, f"+{due_days} days"))

                    _log_isa95(conn, "L4_to_L3", "ProductionSchedule", "ERP", "MES",
                               f"New SO {so_id}: {prod[0]} x {qty} KFT for {cust}", so_id)

            # ── 2. Order-to-Cash Progression (every tick, higher throughput) ──

            # Open SOs -> create WO (up to 5 per tick)
            open_sos = conn.execute("""
                SELECT so.sales_order_id, sol.product_id, sol.quantity
                FROM sales_orders so
                JOIN sales_order_lines sol ON so.sales_order_id = sol.sales_order_id
                WHERE so.status = 'Open'
                AND so.sales_order_id NOT IN (SELECT COALESCE(sales_order_id,'') FROM work_orders)
                LIMIT 5
            """).fetchall()
            for so in open_sos:
                wo_count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
                wo_id = f"WO-ERP-{wo_count + 1:04d}"
                conn.execute(
                    """INSERT INTO work_orders (wo_id, product_id, order_qty_kft, priority, due_date, status, created_date, sales_order_id)
                       VALUES (?,?,?,?,date('now','+14 days'),?,datetime('now'),?)""",
                    (wo_id, so[1], so[2], 3, "Released", so[0]))
                conn.execute("UPDATE sales_orders SET status='InProgress' WHERE sales_order_id=?", (so[0],))
                _log_isa95(conn, "L4_to_L3", "ProductionSchedule", "ERP", "MES",
                           f"WO {wo_id} created from SO {so[0]}", wo_id)

            # Completed WOs -> create shipment (up to 5 per tick)
            shippable = conn.execute("""
                SELECT wo.wo_id, wo.sales_order_id, wo.order_qty_kft, so.customer_id
                FROM work_orders wo
                JOIN sales_orders so ON wo.sales_order_id = so.sales_order_id
                WHERE wo.status = 'Complete'
                AND wo.wo_id NOT IN (SELECT COALESCE(wo_id,'') FROM shipments)
                AND so.status NOT IN ('Shipped','Invoiced')
                LIMIT 5
            """).fetchall()
            for wo in shippable:
                ship_count = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
                ship_id = f"SHIP-ERP-{ship_count + 1:04d}"
                carriers = ["FedEx Freight", "UPS Freight", "YRC", "Old Dominion"]
                conn.execute(
                    "INSERT INTO shipments (shipment_id,sales_order_id,wo_id,customer_id,carrier,qty_shipped,status) VALUES (?,?,?,?,?,?,?)",
                    (ship_id, wo[1], wo[0], wo[3], random.choice(carriers), wo[2], "Shipped"))
                conn.execute("UPDATE sales_orders SET status='Shipped' WHERE sales_order_id=?", (wo[1],))
                _log_isa95(conn, "L3_to_L4", "ProductionPerformance", "MES", "ERP",
                           f"Shipped {ship_id} for WO {wo[0]}", ship_id)

            # Shipped -> create invoice (up to 5 per tick)
            invoiceable = conn.execute("""
                SELECT s.shipment_id, s.sales_order_id, s.customer_id, s.qty_shipped,
                       sol.unit_price
                FROM shipments s
                JOIN sales_order_lines sol ON s.sales_order_id = sol.sales_order_id
                WHERE s.status = 'Shipped'
                AND s.sales_order_id NOT IN (SELECT COALESCE(sales_order_id,'') FROM invoices)
                LIMIT 5
            """).fetchall()
            for s in invoiceable:
                inv_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
                inv_id = f"INV-ERP-{inv_count + 1:04d}"
                subtotal = round((s[3] or 1) * (s[4] or 50), 2)
                tax = round(subtotal * 0.07, 2)
                conn.execute(
                    "INSERT INTO invoices (invoice_id,sales_order_id,customer_id,subtotal,tax,total,due_date,status) VALUES (?,?,?,?,?,?,date('now','+30 days'),?)",
                    (inv_id, s[1], s[2], subtotal, tax, round(subtotal + tax, 2), "Sent"))
                _log_isa95(conn, "L3_to_L4", "InventoryCount", "MES", "ERP",
                           f"Invoice {inv_id}: ${round(subtotal + tax, 2)}", inv_id)

            # Age invoices: Sent > 30 days -> Paid (70%) or Overdue (30%)
            aging = conn.execute(
                "SELECT invoice_id FROM invoices WHERE status='Sent' AND due_date < date('now')").fetchall()
            for inv in aging:
                new_status = "Paid" if random.random() < 0.7 else "Overdue"
                conn.execute("UPDATE invoices SET status=?, payment_date=datetime('now') WHERE invoice_id=?",
                             (new_status, inv[0]))

            # ── 3. Financial Posting for completed WOs (every tick) ────
            unposted = conn.execute("""
                SELECT wo.wo_id, wo.order_qty_kft, p.revenue_per_kft, p.cost_per_kft, wo.actual_end
                FROM work_orders wo JOIN products p ON wo.product_id = p.product_id
                WHERE wo.status = 'Complete' AND wo.actual_end IS NOT NULL
                AND wo.wo_id NOT IN (SELECT reference_id FROM financial_ledger WHERE reference_type='WO' AND account_type='Revenue')
                LIMIT 10
            """).fetchall()
            for wo in unposted:
                qty = wo[1] or 1
                rev = round(qty * (wo[2] or 50), 2)
                cogs = round(qty * (wo[3] or 30), 2)
                period = wo[4][:7] if wo[4] else datetime.now().strftime("%Y-%m")
                conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                             (wo[4] or datetime.now().strftime("%Y-%m-%d"), "Revenue", "WO", wo[0], rev, f"Revenue: {wo[0]}", period))
                conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                             (wo[4] or datetime.now().strftime("%Y-%m-%d"), "COGS", "WO", wo[0], cogs, f"COGS: {wo[0]}", period))

            # ── 4. Procure-to-Pay (every 3 ticks) ────────────────────
            if _tick > 0 and _tick % 3 == 0:
                # Check materials below safety stock -> create PO
                low_stock = conn.execute("""
                    SELECT m.material_id, m.name, m.unit_cost, m.supplier,
                           COALESCE(SUM(i.qty_on_hand - i.qty_allocated), 0) AS available,
                           COALESCE(b.min_level, 50) AS safety
                    FROM materials m
                    LEFT JOIN inventory i ON i.material_id = m.material_id
                    LEFT JOIN buffer_inventory b ON b.material_id = m.material_id
                    GROUP BY m.material_id
                    HAVING available < safety * 1.2
                    LIMIT 3
                """).fetchall()
                for mat in low_stock:
                    existing = conn.execute(
                        "SELECT po_id FROM purchase_orders WHERE material_id=? AND status IN ('Draft','Approved','Sent')",
                        (mat[0],)).fetchone()
                    if not existing:
                        total_pos += 1
                        po_id = f"PO-ERP-{total_pos:04d}"
                        qty = max(100, int(mat[5] * 2))
                        conn.execute(
                            """INSERT INTO purchase_orders (po_id,supplier,material_id,quantity,unit_cost,total_cost,
                               expected_delivery,status,created_by) VALUES (?,?,?,?,?,?,date('now','+14 days'),?,?)""",
                            (po_id, mat[3] or "Unknown", mat[0], qty, mat[2],
                             round(qty * mat[2], 2), "Approved", "ERP_SIM"))
                        _log_isa95(conn, "L4_to_L3", "MaterialRequirement", "ERP", "MES",
                                   f"PO {po_id}: {mat[1]} x {qty} from {mat[3]}", po_id)

                # Process goods receipts for POs past expected delivery
                receivable = conn.execute("""
                    SELECT po_id, material_id, quantity, unit_cost, supplier
                    FROM purchase_orders
                    WHERE status IN ('Approved','Sent') AND expected_delivery <= date('now')
                    LIMIT 3
                """).fetchall()
                for po in receivable:
                    accept_rate = random.uniform(0.93, 1.0)
                    accepted = int(po[2] * accept_rate)
                    rejected = int(po[2]) - accepted
                    result = "Pass" if accept_rate > 0.97 else "Conditional"
                    lot = f"GR-LOT-{random.randint(10000,99999)}"

                    conn.execute(
                        """INSERT INTO goods_receipts (po_id,material_id,qty_received,qty_accepted,qty_rejected,
                           inspector,inspection_result,lot_number) VALUES (?,?,?,?,?,?,?,?)""",
                        (po[0], po[1], int(po[2]), accepted, rejected, f"QA-{random.randint(1,5)}", result, lot))
                    conn.execute("UPDATE purchase_orders SET status='Received', actual_delivery=datetime('now') WHERE po_id=?",
                                 (po[0],))
                    existing_inv = conn.execute(
                        "SELECT inv_id, qty_on_hand FROM inventory WHERE material_id=? LIMIT 1",
                        (po[1],)).fetchone()
                    if existing_inv:
                        conn.execute("UPDATE inventory SET qty_on_hand = qty_on_hand + ? WHERE inv_id=?",
                                     (accepted, existing_inv[0]))
                    _log_isa95(conn, "L3_to_L4", "MaterialReceipt", "MES", "ERP",
                               f"GR for PO {po[0]}: {accepted} accepted, {rejected} rejected", po[0])

            # ── 5. Demand Forecast (every 5 ticks) ────────────────────
            if _tick > 0 and _tick % 5 == 0:
                from engines.forecast import ses_forecast
                families = [r[0] for r in conn.execute("SELECT DISTINCT family FROM products").fetchall()]
                for fam in families:
                    actuals_rows = conn.execute("""
                        SELECT COALESCE(SUM(sol.quantity), 0) AS total_qty
                        FROM sales_order_lines sol
                        JOIN products p ON sol.product_id = p.product_id
                        WHERE p.family = ?
                        GROUP BY strftime('%W', sol.promised_date)
                        ORDER BY sol.promised_date DESC LIMIT 8
                    """, (fam,)).fetchall()
                    actuals = [r[0] for r in reversed(actuals_rows)] if actuals_rows else [10]

                    forecasts = ses_forecast(actuals, alpha=0.3, periods_ahead=1)
                    if forecasts:
                        next_forecast = forecasts[-1]
                        conn.execute(
                            "INSERT INTO demand_forecast (product_family,period_start,period_type,forecast_qty,forecast_method,alpha) VALUES (?,date('now'),'week',?,?,?)",
                            (fam, next_forecast, "SES", 0.3))

                sim_week += 1

            # Update state
            _set_state(conn, "sim_week", sim_week)
            _set_state(conn, "total_orders_generated", total_orders)
            _set_state(conn, "total_pos_created", total_pos)
            _set_state(conn, "sim_date", datetime.now().strftime("%Y-%m-%d"))

            conn.commit()
            conn.close()
            _tick += 1
        except Exception:
            pass
        # Sleep after tick — first tick executes immediately on start
        time.sleep(interval)


def start(db_path, interval=10):
    """Start the ERP simulator background thread."""
    global _running, _thread, _tick
    if _running:
        return False
    _running = True
    _tick = 0
    _thread = threading.Thread(target=_run, args=(db_path, interval), daemon=True)
    _thread.start()
    return True


def stop():
    """Stop the ERP simulator."""
    global _running
    _running = False
    return True


def is_running():
    """Check if simulator is running."""
    return _running


def get_tick():
    """Return current tick count."""
    return _tick
