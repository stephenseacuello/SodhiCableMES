#!/usr/bin/env python3
"""SodhiCable MES v4.0 — Database Initializer. Run: python init_db.py"""
import os, sys, sqlite3, random
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "sodhicable_mes.db")


def execute_sql_file(conn, filepath, label):
    if not os.path.exists(filepath):
        print(f"  WARNING: {label} not found at {filepath}")
        return
    with open(filepath, "r") as f:
        sql = f.read()
    try:
        conn.executescript(sql)
        print(f"  OK: {label}")
    except sqlite3.Error as e:
        print(f"  ERROR in {label}: {e}")
        raise


def seed_extra_data(conn):
    """Seed data that isn't in the SQL files (print marking, reason codes, etc.)."""
    random.seed(55)
    base = datetime(2026, 4, 1)

    # --- Reason codes for downtime ---
    reason_codes = [
        ("Breakdown", "BK-MOTOR", "Motor failure / overheating", 0),
        ("Breakdown", "BK-BELT", "Belt snap or wear", 0),
        ("Breakdown", "BK-SENSOR", "Sensor fault / miscalibration", 0),
        ("Breakdown", "BK-DIE", "Drawing die wear / breakage", 0),
        ("Breakdown", "BK-BEARING", "Bearing seizure", 0),
        ("Breakdown", "BK-PLC", "PLC / control fault", 0),
        ("Breakdown", "BK-LEAK", "Crosshead leak / seal failure", 0),
        ("Setup", "SU-PRODUCT", "Product changeover", 1),
        ("Setup", "SU-DIE", "Die change", 1),
        ("Setup", "SU-COLOR", "Compound color change", 1),
        ("Setup", "SU-TOOL", "Tooling swap", 1),
        ("MaterialWait", "MW-COPPER", "Copper rod delayed", 0),
        ("MaterialWait", "MW-COMPOUND", "Compound shortage", 0),
        ("MaterialWait", "MW-FOIL", "Foil/tape stock out", 0),
        ("QualityHold", "QH-SPARK", "Spark test failure", 0),
        ("QualityHold", "QH-DIM", "Dimensional out of spec", 0),
        ("QualityHold", "QH-NCR", "NCR review pending", 0),
        ("PM", "PM-CAL", "Scheduled calibration", 1),
        ("PM", "PM-LUBE", "Lubrication", 1),
        ("PM", "PM-FILTER", "Filter replacement", 1),
        ("PM", "PM-INSPECT", "Preventive inspection", 1),
        ("NoOrders", "NO-QUEUE", "No orders in queue", 0),
        ("NoOrders", "NO-SCHED", "Awaiting schedule release", 0),
        ("Other", "OT-TRAIN", "Training", 1),
        ("Other", "OT-SAFETY", "Safety meeting", 1),
        ("Other", "OT-POWER", "Power outage", 0),
    ]
    for cat, code, desc, planned in reason_codes:
        conn.execute("INSERT OR IGNORE INTO reason_codes (category, reason_code, description, is_planned) VALUES (?,?,?,?)",
                     (cat, code, desc, planned))

    # --- Scrap reason sub-codes ---
    scrap_codes = [
        ("STARTUP", "ST-PURGE", "Purge material at line start", "Reduce purge volume"),
        ("STARTUP", "ST-ADJUST", "Initial adjustment scrap", "Pre-set recipe parameters"),
        ("CHANGEOVER", "CO-COMPOUND", "Compound transition scrap", "Minimize compound mixing"),
        ("CHANGEOVER", "CO-COLOR", "Color change purge", "Schedule dark-to-light"),
        ("SPARK_FAULT", "SF-PINHOLE", "Insulation pinhole detected", "Check die condition"),
        ("SPARK_FAULT", "SF-VOID", "Void in insulation", "Verify compound moisture"),
        ("OD_EXCURSION", "OD-HIGH", "OD above spec", "Reduce screw RPM"),
        ("OD_EXCURSION", "OD-LOW", "OD below spec", "Increase screw RPM"),
        ("MATERIAL_DEFECT", "MD-COPPER", "Copper rod surface defect", "Incoming inspection"),
        ("MATERIAL_DEFECT", "MD-COMPOUND", "Compound contamination", "Supplier corrective action"),
        ("COMPOUND_BLEED", "CB-PLASTICIZER", "Plasticizer bleed-out", "Adjust compound formula"),
        ("COMPOUND_BLEED", "CB-MOISTURE", "Moisture in compound", "Pre-dry compound"),
    ]
    for cause, sub, desc, action in scrap_codes:
        conn.execute("INSERT OR IGNORE INTO scrap_reason_codes (cause_code, sub_code, description, corrective_action) VALUES (?,?,?,?)",
                     (cause, sub, desc, action))

    # --- Documents ---
    docs = [
        ("TM","TM-001","Technical Manual: CV Extrusion PVC","Rev D","Active","2025-06-01"),
        ("TM","TM-002","Technical Manual: Wire Drawing","Rev C","Active","2025-03-15"),
        ("TM","TM-003","Technical Manual: FEP Extrusion","Rev B","Active","2026-01-10"),
        ("TM","TM-004","Technical Manual: Braiding Operations","Rev B","Active","2025-07-15"),
        ("TM","TM-005","Technical Manual: AIA Armoring","Rev C","Active","2025-09-01"),
        ("TM","TM-006","Technical Manual: CCCW Operations","Rev A","Active","2025-12-01"),
        ("TM","TM-007","Technical Manual: MV Cable Testing","Rev A","Active","2026-04-01"),
        ("SOP","SOP-001","SOP: Spark Testing","Rev E","Active","2024-11-01"),
        ("SOP","SOP-002","SOP: Reel Packaging","Rev C","Active","2025-02-15"),
        ("SOP","SOP-003","SOP: Shift Handoff","Rev B","Active","2025-08-01"),
        ("SOP","SOP-004","SOP: NCR Process","Rev D","Active","2025-05-01"),
        ("SOP","SOP-005","SOP: CUSUM Monitoring","Rev A","Active","2026-02-01"),
        ("SOP","SOP-006","SOP: Compound Mixing","Rev C","Active","2024-08-01"),
        ("SOP","SOP-007","SOP: Die Change","Rev B","Active","2026-03-15"),
        ("Drawing","DWG-001","Assembly Drawing: INST-3C16-FBS","Rev A","Active","2025-01-15"),
        ("Drawing","DWG-002","Assembly Drawing: CTRL-2C12-XA","Rev B","Active","2025-04-01"),
        ("Drawing","DWG-003","Assembly Drawing: DHT-1C12-260","Rev A","Active","2025-11-15"),
        ("Certificate","CERT-001","UL Listing Certificate: UL2196 Series","2024","Active","2024-06-01"),
        ("Certificate","CERT-002","MIL-DTL-24643 QPL Certificate","2025","Active","2025-01-15"),
        ("MILSpec","MIL-001","MIL-DTL-24643/29 Wire Spec","Rev G","Active","2023-09-01"),
        ("MILSpec","MIL-002","MIL-C-24640 Cable Spec","Rev F","Active","2024-03-15"),
        ("Recipe","RCP-DOC-001","Recipe Document: CV1 PVC Extrusion","Rev D","Active","2025-06-01"),
        ("Recipe","RCP-DOC-002","Recipe Document: PX1 FEP Extrusion","Rev A","Active","2026-01-10"),
    ]
    for doc_type, doc_name, title, rev, status, eff_date in docs:
        conn.execute("INSERT INTO documents (doc_type, doc_name, version, revision, status, effective_date, notes) VALUES (?,?,'1.0',?,?,?,?)",
                     (doc_type, doc_name, rev, status, eff_date, title))

    # Recipe ingredients
    ingredients = [
        (1,"MAT-001",15.0,"kg",0.03),(1,"MAT-004",8.5,"kg",0.02),(1,"MAT-010",2.0,"roll",0.01),
        (2,"MAT-001",20.0,"kg",0.03),(2,"MAT-005",12.0,"kg",0.02),
        (3,"MAT-002",12.0,"kg",0.03),(3,"MAT-006",5.0,"kg",0.02),
        (4,"MAT-001",14.0,"kg",0.03),(4,"MAT-004",7.0,"kg",0.02),
        (5,"MAT-001",8.0,"kg",0.02),(5,"MAT-004",4.0,"kg",0.02),(5,"MAT-015",2.0,"kg",0.02),
    ]
    for rid, mid, qty, uom, scrap in ingredients:
        conn.execute("INSERT OR IGNORE INTO recipe_ingredients (recipe_id, material_id, qty_per_kft, uom, scrap_allowance) VALUES (?,?,?,?,?)",
                     (rid, mid, qty, uom, scrap))

    # --- Maintenance Schedule (Gap #6) ---
    equip_rows = conn.execute("SELECT equipment_id, work_center_id, equipment_type FROM equipment").fetchall()
    for eq in equip_rows:
        eid, wc, etype = eq[0], eq[1], eq[2]
        # PM frequencies by type
        if etype in ("Screw", "Motor"):
            pms = [("Preventive", 30), ("Calibration", 90)]
        elif etype in ("Die", "Bearing"):
            pms = [("Preventive", 14), ("Calibration", 60)]
        elif etype == "Sensor":
            pms = [("Calibration", 30)]
        else:
            pms = [("Preventive", 60)]
        for pm_type, freq in pms:
            # Spread next_due relative to today: ~30% overdue, ~20% due soon, ~50% OK
            from datetime import date as _date
            today = _date.today()
            offset = random.randint(-freq, freq)  # range from -freq to +freq days from today
            nxt_date = today + timedelta(days=offset)
            last_date = nxt_date - timedelta(days=freq)
            last = last_date.strftime("%Y-%m-%d")
            nxt = nxt_date.strftime("%Y-%m-%d")
            tech = random.choice([9, 17, 27, 33])  # maintenance personnel
            conn.execute("INSERT INTO maintenance_schedule (equipment_id, pm_type, frequency_days, last_performed, next_due, assigned_to) VALUES (?,?,?,?,?,?)",
                         (eid, pm_type, freq, last, nxt, tech))

    # Sync equipment.last_pm_date and next_pm_date from maintenance_schedule
    conn.execute("""
        UPDATE equipment SET
            last_pm_date = (SELECT MAX(ms.last_performed) FROM maintenance_schedule ms WHERE ms.equipment_id = equipment.equipment_id),
            next_pm_date = (SELECT MIN(ms.next_due) FROM maintenance_schedule ms WHERE ms.equipment_id = equipment.equipment_id)
        WHERE equipment_id IN (SELECT DISTINCT equipment_id FROM maintenance_schedule)
    """)

    # --- Test Results (Gap #12) ---
    test_types = [
        ("Spark", "UL 2556", "kV", 2.5, 4.0, 3.0),
        ("Hipot", "UL 2556", "kV", 0, 50.0, 15.0),
        ("Resistance", "ASTM B8", "ohm/kft", 0, 5.0, 1.2),
        ("Dimensional", "Internal", "in", 0.040, 0.070, 0.055),
        ("Tensile", "ASTM D470", "psi", 1500, 99999, 2800),
    ]
    completed_wos = conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status IN ('Complete','InProcess')").fetchall()
    for wo in completed_wos:
        for tt, spec, uom, lo, hi, typical in test_types:
            val = round(random.gauss(typical, (hi - lo) * 0.05), 2)
            pf = "PASS" if lo <= val <= hi else "FAIL"
            t = base + timedelta(days=random.randint(0, 14))
            conn.execute("INSERT INTO test_results (wo_id, product_id, test_type, test_spec, test_value, test_uom, lower_limit, upper_limit, pass_fail, test_date, tester_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (wo[0], wo[1], tt, spec, val, uom, lo, hi, pf, t.strftime("%Y-%m-%d"), random.choice([6, 7, 16, 26])))

    # --- Test Protocols (Gap #13) ---
    protocols = [
        ("INST-3C16-FBS", 1, "Spark", "UL 2556", "100%", "≤2.5kV/mil+1kV", "Hold"),
        ("INST-3C16-FBS", 2, "Resistance", "ASTM B8", "PerLot", "≤1.5 ohm/kft", "Hold"),
        ("INST-3C16-FBS", 3, "Dimensional", "Internal", "PerReel", "OD ±0.003in", "Hold"),
        ("CTRL-2C12-XA", 1, "Spark", "UL 2556", "100%", "≤2.5kV/mil+1kV", "Hold"),
        ("CTRL-2C12-XA", 2, "Tensile", "ASTM D470", "PerLot", "≥1500 psi", "Hold"),
        ("DHT-1C12-260", 1, "Spark", "API", "100%", "≤3kV/mil", "Hold"),
        ("DHT-1C12-260", 2, "Hipot", "API", "PerReel", "15kV 1min", "Hold"),
        ("LSOH-3C12-SB", 1, "Spark", "MIL-DTL-24643", "100%", "≤2kV/mil+1kV", "Hold"),
        ("LSOH-3C12-SB", 2, "Resistance", "MIL-DTL-24643", "PerLot", "≤1.0 ohm/kft", "Hold"),
        ("UL2196-2C14", 1, "Spark", "UL 2556", "100%", "≤2.5kV/mil+1kV", "Hold"),
        ("IC-10AWG-THHN", 1, "Spark", "UL 83", "100%", "≤2kV", "Hold"),
    ]
    for pid, seq, tt, spec, freq, criteria, action in protocols:
        conn.execute("INSERT INTO test_protocols (product_id, test_sequence, test_type, spec_reference, frequency, pass_criteria, fail_action) VALUES (?,?,?,?,?,?,?)",
                     (pid, seq, tt, spec, freq, criteria, action))

    # --- Operations from Routings × WOs (Gap #14) ---
    wos_data = conn.execute("SELECT wo_id, product_id, order_qty_kft, status, due_date, created_date FROM work_orders").fetchall()
    for wo in wos_data:
        wo_id, prod_id, qty_kft, wo_status = wo[0], wo[1], wo[2], wo[3]
        rtgs = conn.execute("SELECT routing_id, sequence_num, wc_id, operation_name, process_time_min_per_100ft, setup_time_min FROM routings WHERE product_id = ? ORDER BY sequence_num", (prod_id,)).fetchall()
        for rtg in rtgs:
            r_id, seq, wc, op_name, proc_time, setup = rtg[0], rtg[1], rtg[2], rtg[3], rtg[4], rtg[5] or 0
            if wo_status == "Complete":
                op_status = "Complete"
            elif wo_status == "InProcess" and seq <= 3:
                op_status = "Complete"
            elif wo_status == "InProcess":
                op_status = "InProcess" if seq == 4 else "Pending"
            else:
                op_status = "Pending"
            qty_good = qty_kft * 1000 * 0.97 if op_status == "Complete" else 0
            qty_scrap = qty_kft * 1000 * 0.03 if op_status == "Complete" else 0
            run_min = proc_time * qty_kft * 10 if op_status == "Complete" else 0
            conn.execute("""INSERT INTO operations (wo_id, routing_id, step_sequence, wc_id, operation_name, status, qty_good, qty_scrap, setup_time_min, run_time_min)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                         (wo_id, r_id, seq, wc, op_name or f"Step {seq}", op_status, qty_good, qty_scrap, setup, run_min))

    # --- Sales Orders (Gap #15) ---
    cust_ids = [r[0] for r in conn.execute("SELECT customer_id FROM customers").fetchall()]
    for i, wo in enumerate(wos_data[:15]):
        so_id = f"SO-2026-{i+1:03d}"
        cust = cust_ids[i % len(cust_ids)]
        wo_id, prod_id, qty, wo_st, due, created = wo[0], wo[1], wo[2], wo[3], wo[4], wo[5]
        so_status = "Shipped" if wo_st == "Complete" else "Open"
        conn.execute("INSERT OR IGNORE INTO sales_orders (sales_order_id, customer_id, order_date, required_date, priority, status, business_unit) VALUES (?,?,?,?,?,?,?)",
                     (so_id, cust, created, due, 5, so_status, "Industrial"))
        conn.execute("INSERT INTO sales_order_lines (sales_order_id, product_id, quantity, promised_date) VALUES (?,?,?,?)",
                     (so_id, prod_id, qty, due))
        conn.execute("UPDATE work_orders SET sales_order_id = ? WHERE wo_id = ?", (so_id, wo_id))

    # --- Buffer Inventory (Gap #16) ---
    buffers = [
        ("MAT-001", None, "Raw-to-L1", 200, 800, 300, "kg"),
        ("MAT-004", None, "Raw-to-L1", 100, 500, 200, "kg"),
        ("MAT-005", None, "Raw-to-L1", 80, 400, 150, "kg"),
        ("MAT-006", None, "Raw-to-L1", 50, 250, 100, "kg"),
        ("MAT-008", None, "Raw-to-L1", 50, 300, 100, "kg"),
        ("MAT-009", None, "Raw-to-L1", 100, 500, 200, "kg"),
        (None, "INST-3C16-FBS", "L1-to-L2", 20, 100, 40, "KFT"),
        (None, "CTRL-2C12-XA", "L1-to-L2", 15, 80, 30, "KFT"),
        (None, "IC-10AWG-THHN", "L1-to-L2", 50, 500, 200, "KFT"),
        (None, "UL2196-2C14", "L1-to-L2", 20, 100, 40, "KFT"),
    ]
    for mat, prod, tier, mn, mx, reorder, uom in buffers:
        current = random.randint(mn, mx)
        conn.execute("INSERT INTO buffer_inventory (material_id, product_id, tier_boundary, min_level, max_level, reorder_qty, current_qty, uom, last_replenished) VALUES (?,?,?,?,?,?,?,?,?)",
                     (mat, prod, tier, mn, mx, reorder, current, uom, (base - timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")))

    # --- Inventory (Gap #17) ---
    materials = conn.execute("SELECT material_id, uom FROM materials").fetchall()
    for mat in materials:
        lot = f"LOT-{mat[0]}-{random.randint(100,999)}"
        qty = random.randint(100, 1000)
        alloc = random.randint(0, qty // 3)
        exp = (base + timedelta(days=random.randint(7, 90))).strftime("%Y-%m-%d") if "Compound" in (conn.execute("SELECT material_type FROM materials WHERE material_id=?", (mat[0],)).fetchone()[0] or "") else None
        conn.execute("INSERT INTO inventory (material_id, location_code, lot_number, qty_on_hand, qty_allocated, uom, receipt_date, expiration_date, fifo_date, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (mat[0], random.choice(["WH-A","WH-B","WH-C","FLOOR"]), lot, qty, alloc, mat[1], (base - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"), exp, (base - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"), "Available"))

    # --- Dispatch Queue (Gap #20) ---
    released_wos = conn.execute("SELECT wo_id, product_id, priority, due_date FROM work_orders WHERE status = 'Released'").fetchall()
    for wo in released_wos:
        # Assign to first routing WC
        first_wc = conn.execute("SELECT wc_id FROM routings WHERE product_id = ? ORDER BY sequence_num LIMIT 1", (wo[1],)).fetchone()
        wc = first_wc[0] if first_wc else "DRAW-1"
        score = round(0.4 * (1.0 / max(wo[2], 1)) + 0.4 * wo[2] + 0.2 * random.uniform(0.5, 2.0), 2)
        conn.execute("INSERT INTO dispatch_queue (wo_id, wc_id, priority_score, queue_position, status) VALUES (?,?,?,?,?)",
                     (wo[0], wc, score, random.randint(1, 10), "Waiting"))

    # --- Compliance Workflows (Gap #24) ---
    workflows = [
        ("MIL-Spec Compliance", "MIL-Spec", "S", "WO Created for MIL product", "Verify QPL;Download recipe;100% spark test;DC resistance;Certificate of Conformance", "MIL-DTL-24643,Certificate"),
        ("UL Listing Compliance", "UL-Listed", "U", "WO Created for UL2196 product", "Verify UL file;FT4 flame test;VW-1 test;Print marking verification;UL label", "UL 2196,UL 2556"),
        ("API Compliance", "API", "C", "WO Created for API product", "Verify API spec;Hipot test;H2S resistance;Certificate of Analysis", "API 5L,Certificate"),
        ("Certificate of Conformance", "CoC", None, "Shipment created", "Compile test results;Generate CoC;QA review;Sign-off;Attach to shipment", "CoC template"),
        ("NCR Workflow", "NCR", None, "NCR opened", "Document defect;Root cause analysis;Corrective action;Verification;Close NCR", "NCR form,CAPA form"),
        ("Hold/Release", "Hold", None, "Quality hold placed", "Document hold reason;MRB review;Disposition;Release or scrap;Update lot status", "Hold form"),
    ]
    for name, wtype, fam, trigger, steps, docs in workflows:
        conn.execute("INSERT INTO compliance_workflows (workflow_name, workflow_type, product_family, trigger_event, steps, required_docs) VALUES (?,?,?,?,?,?)",
                     (name, wtype, fam, trigger, steps, docs))

    # --- Seed remaining empty tables ---

    # audit_trail: WO status changes and recipe version changes
    for wo in conn.execute("SELECT wo_id, status, created_date FROM work_orders WHERE status IN ('Complete','InProcess')").fetchall():
        conn.execute("INSERT INTO audit_trail (table_name, record_id, field_changed, old_value, new_value, changed_datetime, change_reason) VALUES (?,?,?,?,?,?,?)",
                     ("work_orders", wo[0], "status", "Pending", wo[1], wo[2], "WO status transition"))
    for r in conn.execute("SELECT recipe_id, recipe_code, version FROM recipes").fetchall():
        conn.execute("INSERT INTO audit_trail (table_name, record_id, field_changed, old_value, new_value, changed_datetime, change_reason) VALUES (?,?,?,?,?,?,?)",
                     ("recipes", str(r[0]), "version", str(max(1, r[2]-1)), str(r[2]), (base - timedelta(days=random.randint(30,180))).strftime("%Y-%m-%d"), "Recipe version update"))

    # bom_products: multi-level product BOM (cable → conductors)
    bom_prods = [
        ("INST-3C16-FBS", "IC-12AWG-XLPE", 3.0), ("INST-12P22-OS", "IC-12AWG-XLPE", 24.0),
        ("CTRL-2C12-XA", "IC-12AWG-XLPE", 2.0), ("CTRL-4C12-XA", "IC-12AWG-XLPE", 4.0),
        ("CTRL-6C14-XA", "IC-12AWG-XLPE", 6.0), ("LSOH-3C12-SB", "IC-12AWG-XLPE", 3.0),
        ("UL2196-2C14", "IC-12AWG-XLPE", 2.0), ("UL2196-4C12", "IC-12AWG-XLPE", 4.0),
    ]
    for parent, child, qty in bom_prods:
        conn.execute("INSERT INTO bom_products (parent_product_id, child_product_id, qty_per, bom_level) VALUES (?,?,?,1)", (parent, child, qty))

    # dispatch_log: historical dispatches for completed WOs
    for wo in conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status = 'Complete'").fetchall():
        first_wc = conn.execute("SELECT wc_id FROM routings WHERE product_id = ? ORDER BY sequence_num LIMIT 1", (wo[1],)).fetchone()
        wc = first_wc[0] if first_wc else "DRAW-1"
        t = base + timedelta(days=random.randint(0, 10))
        conn.execute("INSERT INTO dispatch_log (wo_id, wc_id, operator_id, dispatch_time, completion_time, priority_score) VALUES (?,?,?,?,?,?)",
                     (wo[0], wc, random.randint(1, 12), t.strftime("%Y-%m-%d 07:30"), (t + timedelta(hours=random.randint(4, 16))).strftime("%Y-%m-%d %H:%M"), round(random.uniform(2, 8), 2)))

    # document_links: map all 23 docs to products/WCs
    doc_ids = [r[0] for r in conn.execute("SELECT doc_id FROM documents").fetchall()]
    prod_ids = [r[0] for r in conn.execute("SELECT product_id FROM products LIMIT 10").fetchall()]
    wc_ids = ["DRAW-1", "CV-1", "CV-2", "PLCV-1", "PX-1", "TEST-1", "CABLE-1", "COMPOUND-1"]
    for did in doc_ids:
        conn.execute("INSERT INTO document_links (doc_id, linked_entity_type, linked_entity_id, link_type) VALUES (?,?,?,?)",
                     (did, random.choice(["Product", "WorkCenter"]), random.choice(prod_ids + wc_ids), random.choice(["Governs", "References", "Requires"])))

    # kpis: weekly KPI snapshots
    for week in range(2):
        d = base + timedelta(weeks=week)
        for kpi_name, val, target, unit in [("OEE", round(random.uniform(72,82),1), 85, "%"), ("FPY", round(random.uniform(95,98),1), 97, "%"), ("Schedule_Adherence", round(random.uniform(88,96),1), 90, "%"), ("Labor_Efficiency", round(random.uniform(60,75),1), 85, "%"), ("MTBF", round(random.uniform(400,600),0), 500, "hrs"), ("Scrap_Rate", round(random.uniform(0.1,0.5),2), 3, "%")]:
            conn.execute("INSERT INTO kpis (kpi_name, kpi_value, target_value, measurement_date, unit, status) VALUES (?,?,?,?,?,?)",
                         (kpi_name, val, target, d.strftime("%Y-%m-%d"), unit, "Tracking"))

    # maintenance: completed PM work orders
    for eq in conn.execute("SELECT equipment_id, work_center_id FROM equipment").fetchall():
        for i in range(random.randint(1, 3)):
            t = base - timedelta(days=random.randint(1, 60))
            dur = round(random.uniform(0.5, 4.0), 1)
            conn.execute("INSERT INTO maintenance (equipment_id, wc_id, maint_type, scheduled_date, completed_date, duration_hours, technician, performed_by, result, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (eq[0], eq[1], random.choice(["PM", "Calibration", "PM"]), t.strftime("%Y-%m-%d"), t.strftime("%Y-%m-%d"), dur, f"Tech-{random.randint(1,5)}", random.choice([9,17,27,33]), "Pass", "Complete"))

    # recipe_download_log: operator acknowledged recipe before starting
    for wo in conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status IN ('Complete','InProcess')").fetchall():
        recipe = conn.execute("SELECT recipe_id FROM recipes WHERE product_id = ? LIMIT 1", (wo[1],)).fetchone()
        if recipe:
            t = base + timedelta(days=random.randint(0, 7))
            conn.execute("INSERT INTO recipe_download_log (operation_id, recipe_id, download_datetime, acknowledged_by, acknowledged_at) VALUES (?,?,?,?,?)",
                         (None, recipe[0], t.strftime("%Y-%m-%d 07:15"), random.randint(1, 12), t.strftime("%Y-%m-%d 07:16")))

    # schedule: scheduled jobs for released/inprocess WOs
    for wo in conn.execute("SELECT wo_id, product_id FROM work_orders WHERE status IN ('Released','InProcess')").fetchall():
        rtgs = conn.execute("SELECT wc_id, sequence_num FROM routings WHERE product_id = ? ORDER BY sequence_num", (wo[1],)).fetchall()
        for rtg in rtgs:
            conn.execute("INSERT INTO schedule (wo_id, wc_id, sequence_pos, status) VALUES (?,?,?,?)",
                         (wo[0], rtg[0], rtg[1], "Planned"))

    # schedule_results: historical solver runs
    for algo in ["WSPT", "EDD", "LP_ProductMix", "LPT_Parallel", "Johnson_FlowShop"]:
        t = base + timedelta(days=random.randint(0, 7))
        conn.execute("INSERT INTO schedule_results (run_datetime, algorithm, objective_func, objective_value, num_jobs, solve_time_sec) VALUES (?,?,?,?,?,?)",
                     (t.strftime("%Y-%m-%d %H:%M"), algo, "MinMakespan" if "SPT" in algo or "EDD" in algo else "MaxProfit", round(random.uniform(10000, 200000), 1), random.randint(5, 25), round(random.uniform(0.1, 5.0), 2)))

    # scheduler_config: default configs per WC
    sched_configs = [
        ("CABLE-1", "WSPT", "MinWeightedCompletion"), ("CABLE-2", "EDD", "MinLateness"),
        ("CV-1", "EDD", "MinTardiness"), ("CV-2", "SPT", "MinFlowTime"),
        ("DRAW-1", "WSPT", "MinWeightedCompletion"), ("PLCV-1", "EDD", "MinTardiness"),
    ]
    for wc, algo, obj in sched_configs:
        conn.execute("INSERT INTO scheduler_config (wc_id, algorithm, objective_func, is_default) VALUES (?,?,?,1)", (wc, algo, obj))

    # NCR seed data (5 records from "previous shifts")
    ncr_seeds = [
        ("INST-3C16-FBS", "WO-2026-002", "LOT-4502", "Insulation_OD", "Insulation OD exceeded USL on CV-1", "Major", "CV-1"),
        ("CTRL-2C12-XA", "WO-2026-003", "LOT-4505", "Spark_Fault", "Spark test pinhole at 1247 ft", "Critical", "TEST-1"),
        ("DHT-2C12-H2S", "WO-2026-006", "LOT-4510", "Diameter_OOS", "Wire diameter trending high on DRAW-1", "Minor", "DRAW-1"),
        ("UL2196-2C14", "WO-2026-007", None, "Print_Marking", "Print legibility fail on UL2196 cable", "Minor", "CUT-1"),
        ("IC-10AWG-THHN", "WO-2026-008", "LOT-4515", "Tensile_Fail", "Jacket tensile below 1500 psi", "Major", "TEST-1"),
    ]
    for pid, woid, lot, defect, desc, sev, wc in ncr_seeds:
        t = base + timedelta(days=random.randint(0, 7))
        conn.execute("INSERT INTO ncr (product_id, wo_id, lot_number, defect_type, description, severity, detected_at, reported_date, status) VALUES (?,?,?,?,?,?,?,?,?)",
                     (pid, woid, lot, defect, desc, sev, wc, t.strftime("%Y-%m-%d"), random.choice(["Open", "Open", "InReview", "Closed"])))

    # Add BOM materials for all products without BOM
    bom_tmpls = {
        "A":[("MAT-001",15,"kg"),("MAT-004",8,"kg"),("MAT-010",2,"roll"),("MAT-008",6,"kg"),("MAT-012",1.5,"kg")],
        "B":[("MAT-001",20,"kg"),("MAT-005",12,"kg"),("MAT-008",8,"kg"),("MAT-009",10,"kg")],
        "C":[("MAT-002",12,"kg"),("MAT-006",5,"kg")],
        "D":[("MAT-002",15,"kg"),("MAT-006",8,"kg"),("MAT-007",3,"kg")],
        "I":[("MAT-001",8,"kg"),("MAT-005",3,"kg")],
        "M":[("MAT-001",30,"kg"),("MAT-005",20,"kg"),("MAT-014",5,"roll")],
        "R":[("MAT-001",10,"kg"),("MAT-004",5,"kg"),("MAT-015",2,"kg")],
        "S":[("MAT-001",18,"kg"),("MAT-016",10,"kg")],
        "U":[("MAT-001",14,"kg"),("MAT-004",7,"kg"),("MAT-011",3,"roll")],
    }
    no_bom = conn.execute("SELECT product_id, family, conductors FROM products WHERE product_id NOT IN (SELECT DISTINCT product_id FROM bom_materials)").fetchall()
    for row in no_bom:
        tmpl = bom_tmpls.get(row[1], bom_tmpls["R"])
        scale = max(1, (row[2] or 1) / 3)
        for mat, qty, uom in tmpl:
            conn.execute("INSERT INTO bom_materials (product_id, material_id, qty_per_kft, uom, scrap_factor) VALUES (?,?,?,?,0.02)", (row[0], mat, round(qty*scale,1), uom))

    # Add routings for remaining unrouted products
    unrouted = conn.execute("""SELECT product_id, family FROM products
                              WHERE product_id NOT IN (SELECT DISTINCT product_id FROM routings)""").fetchall()
    route_templates = {
        "A": [("COMPOUND-1",5,45),("DRAW-1",8,30),("CV-1",6,45),("FOIL-1",4,20),("BRAID-1",12,30),("CABLE-1",10,25),("PLCV-1",15,40),("TEST-1",5,10),("CUT-1",3,10),("PACK-1",2,5)],
        "B": [("COMPOUND-1",5,45),("DRAW-1",11,30),("CV-1",9,45),("BRAID-2",16,30),("CABLE-1",14,25),("PLCV-1",20,40),("ARMOR-1",12,35),("TEST-1",7,10),("CUT-1",5,10),("PACK-1",2,5)],
        "C": [("DRAW-1",7,30),("CV-1",5,45),("PX-1",10,60),("TEST-1",4,10),("CUT-1",2,10),("PACK-1",2,5)],
        "S": [("DRAW-1",9,30),("CV-1",7,45),("CABLE-1",12,25),("PLCV-1",17,40),("TEST-1",8,10),("CUT-1",4,10),("PACK-1",3,5)],
        "U": [("COMPOUND-1",5,45),("DRAW-1",9,30),("TAPE-1",6,15),("CV-2",7,45),("CABLE-1",11,25),("PLCV-1",16,40),("CCCW-1",10,30),("TEST-1",6,10),("CUT-1",3,10),("PACK-1",2,5)],
        "R": [("DRAW-1",4,20),("CV-2",3,30),("TEST-1",2,10),("CUT-1",1,5),("PACK-1",1,5)],
        "I": [("DRAW-1",3,20),("CV-2",2,30),("CUT-1",1,5),("PACK-1",1,5)],
        "D": [("DRAW-1",8,30),("CV-1",6,45),("CABLE-1",9,25),("PX-1",12,60),("TEST-1",5,10),("CUT-1",3,10),("PACK-1",2,5)],
        "M": [("DRAW-1",15,30),("CV-1",12,45),("TAPE-1",8,15),("CV-3",12,45),("TEST-1",10,10),("CUT-1",6,10),("PACK-1",4,5)],
    }
    for pid, fam in unrouted:
        template = route_templates.get(fam, route_templates["R"])
        for seq, (wc, proc, setup) in enumerate(template, 1):
            proc_adj = proc * (1 + random.uniform(-0.15, 0.15))  # slight variation
            conn.execute("INSERT INTO routings (product_id, sequence_num, wc_id, operation_name, process_time_min_per_100ft, setup_time_min) VALUES (?,?,?,?,?,?)",
                         (pid, seq, wc, f"Step {seq}", round(proc_adj, 1), setup))

    # --- Bulk work orders (75 more for realistic utilization) ---
    all_prods = conn.execute("SELECT product_id, family, max_order_qty_kft FROM products WHERE product_id IN (SELECT DISTINCT product_id FROM routings)").fetchall()
    bus_units = ["Defense","Industrial","Infrastructure","Oil & Gas"]
    # Heavy on completes so only ~20% are pending/released (creating backlog)
    statuses_w = [("Pending",5),("Released",7),("InProcess",8),("Complete",75),("QCHold",2)]
    current_wo_count = conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
    for i in range(75):
        wo_id = f"WO-2026-{current_wo_count+i+1:03d}"
        prod = random.choice(all_prods)
        pid, fam, max_q = prod[0], prod[1], prod[2] or 500
        # Small quantities: most WOs are 1-5 KFT so utilization stays reasonable
        qty_ranges = {"R":(1,8),"I":(1,8),"A":(1,5),"U":(1,5),"B":(1,3),"C":(1,3),"D":(1,2),"S":(1,2),"M":(1,2)}
        lo, hi = qty_ranges.get(fam, (5,50))
        qty = random.randint(lo, min(hi, int(max_q)))
        bu = random.choice(bus_units)
        priority = random.choices([1,2,3,4,5], weights=[5,10,30,15,10])[0]
        status = random.choices([s[0] for s in statuses_w], weights=[s[1] for s in statuses_w])[0]
        created = base + timedelta(days=random.randint(-5,10))
        due = created + timedelta(days=random.randint(5,21))
        a_start = (created+timedelta(days=1)).strftime("%Y-%m-%d") if status in ("InProcess","Complete") else None
        a_end = (due-timedelta(days=1)).strftime("%Y-%m-%d") if status=="Complete" else None
        conn.execute("INSERT INTO work_orders (wo_id,product_id,business_unit,order_qty_kft,priority,due_date,status,created_date,actual_start,actual_end) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (wo_id,pid,bu,qty,priority,due.strftime("%Y-%m-%d"),status,created.strftime("%Y-%m-%d"),a_start,a_end))
        # Operations
        rtgs = conn.execute("SELECT routing_id,sequence_num,wc_id,operation_name,process_time_min_per_100ft,setup_time_min FROM routings WHERE product_id=? ORDER BY sequence_num",(pid,)).fetchall()
        for r in rtgs:
            seq = r[1]
            op_st = "Complete" if status=="Complete" else "Complete" if status=="InProcess" and seq<=3 else "InProcess" if status=="InProcess" and seq==4 else "Pending"
            proc = (r[4] or 5)*qty*10 if op_st=="Complete" else 0
            conn.execute("INSERT INTO operations (wo_id,routing_id,step_sequence,wc_id,operation_name,status,qty_good,qty_scrap,setup_time_min,run_time_min) VALUES (?,?,?,?,?,?,?,?,?,?)",
                         (wo_id,r[0],seq,r[2],r[3] or f"Step {seq}",op_st,qty*1000*0.97 if op_st=="Complete" else 0,qty*1000*0.03 if op_st=="Complete" else 0,r[5] or 30,proc))
        # Schedule + dispatch
        if status in ("Released","InProcess"):
            for r in rtgs:
                conn.execute("INSERT INTO schedule (wo_id,wc_id,sequence_pos,status) VALUES (?,?,?,?)",(wo_id,r[2],r[1],"Planned"))
        if status=="Released":
            first_wc = rtgs[0][2] if rtgs else "DRAW-1"
            score = round(0.4*(1.0/max(priority,1))+0.4*priority+0.2*random.uniform(0.5,2.0),2)
            conn.execute("INSERT INTO dispatch_queue (wo_id,wc_id,priority_score,queue_position,status) VALUES (?,?,?,?,?)",(wo_id,first_wc,score,random.randint(1,20),"Waiting"))

    # Process deviations (F8 — so page isn't empty)
    dev_seeds = [
        ('WO-2026-002','CV-1','Temperature_F','CUSUM',382.0,365.0,'Warning','PID auto-corrected',1),
        ('WO-2026-002','DRAW-1','WireDiameter_in','CUSUM',0.0259,0.0253,'Minor','Operator notified',1),
        ('WO-2026-006','PX-1','Temperature_F','Threshold',598.0,590.0,'Warning','PID auto-corrected',1),
        ('WO-2026-007','PLCV-1','JacketOD_in','EWMA',0.318,0.310,'Minor','Operator notified',1),
        ('WO-2026-003','CV-1','InsulationOD_in','CUSUM',0.069,0.065,'Major','Job paused',0),
        ('WO-2026-005','PX-1','FEP_OD_mil','Threshold',26.8,25.0,'Critical','Immediate hold',0),
        ('WO-2026-008','CV-2','LineSpeed_fpm','EWMA',2850,3000,'Warning','PID auto-corrected',1),
        ('WO-2026-014','DRAW-1','Tension_lbf','CUSUM',52.0,45.0,'Minor','Operator notified',0),
    ]
    for wo,wc,param,method,val,sp,sev,action,resolved in dev_seeds:
        t = base + timedelta(days=random.randint(0,13), hours=random.randint(7,15))
        conn.execute("INSERT INTO process_deviations (wo_id,wc_id,parameter_name,detection_method,deviation_value,setpoint_value,severity,timestamp,corrective_action,resolved) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (wo,wc,param,method,val,sp,sev,t.strftime("%Y-%m-%d %H:%M:%S"),action,resolved))

    # Hold/release records (F8)
    hold_seeds = [
        ('WO-2026-006','LOT-4510','Spark test failure on reel R-4523','Released'),
        ('WO-2026-003','LOT-4505','Insulation OD exceeded USL on CV-1','Active'),
        ('WO-2026-005',None,'FEP OD critical deviation on PX-1','Active'),
        ('WO-2026-002','LOT-4502','CUSUM drift on DRAW-1 diameter','Released'),
    ]
    for wo,lot,reason,status in hold_seeds:
        t = base + timedelta(days=random.randint(0,10))
        disp = 'Release' if status=='Released' else None
        rel = (t+timedelta(hours=random.randint(2,24))).strftime("%Y-%m-%d %H:%M") if status=='Released' else None
        conn.execute("INSERT INTO hold_release (wo_id,lot_number,hold_reason,held_date,hold_status,disposition,released_date) VALUES (?,?,?,?,?,?,?)",
                     (wo,lot,reason,t.strftime("%Y-%m-%d %H:%M"),status,disp,rel))

    # --- Update completed WOs with actual dates (Gap #8) ---
    conn.execute("""UPDATE work_orders SET actual_start = date(created_date, '+1 day'),
                    actual_end = date(due_date, '-1 day') WHERE status = 'Complete'""")
    conn.execute("""UPDATE work_orders SET actual_start = date(created_date, '+2 day')
                    WHERE status = 'InProcess'""")

    # --- Fix 1: Make ~25% of completed WOs late (actual_end AFTER due_date) ---
    late_wos = conn.execute(
        "SELECT wo_id FROM work_orders WHERE status='Complete' ORDER BY wo_id"
    ).fetchall()
    for i, r in enumerate(late_wos):
        if i % 4 == 0:  # every 4th WO is late by 1-5 days
            days_late = (i % 5) + 1
            conn.execute(
                "UPDATE work_orders SET actual_end = date(due_date, '+' || ? || ' days') WHERE wo_id = ?",
                (days_late, r[0]))

    # --- Fix 2: Lower inventory for some materials below safety stock ---
    conn.execute("UPDATE inventory SET qty_on_hand = 2, qty_allocated = 1 WHERE material_id = 'MAT-001'")
    conn.execute("UPDATE inventory SET qty_on_hand = 0, qty_allocated = 0 WHERE material_id = 'MAT-003'")
    conn.execute("UPDATE inventory SET qty_on_hand = 5, qty_allocated = 4 WHERE material_id = 'MAT-005'")

    # --- Fix 3: Link WOs to sales orders with business units ---
    # Create sales orders for different business units
    bus = [("SO-DEF-001","CUST-001","2026-04-01","2026-04-30",1,"Open","Defense"),
           ("SO-DEF-002","CUST-002","2026-04-05","2026-05-05",2,"Open","Defense"),
           ("SO-INF-001","CUST-005","2026-04-02","2026-04-25",3,"Open","Infrastructure"),
           ("SO-INF-002","CUST-006","2026-04-08","2026-05-01",4,"Open","Infrastructure"),
           ("SO-OG-001","CUST-010","2026-04-03","2026-04-28",2,"Open","Oil & Gas"),
           ("SO-OG-002","CUST-011","2026-04-10","2026-05-10",3,"Open","Oil & Gas"),
           ("SO-IND-001","CUST-015","2026-04-04","2026-04-27",5,"Open","Industrial"),
           ("SO-IND-002","CUST-016","2026-04-12","2026-05-08",4,"Open","Industrial")]
    for so in bus:
        conn.execute(
            "INSERT OR IGNORE INTO sales_orders (sales_order_id,customer_id,order_date,required_date,priority,status,business_unit) VALUES (?,?,?,?,?,?,?)", so)
    # Assign WOs to sales orders round-robin across business units
    all_wos = conn.execute("SELECT wo_id FROM work_orders ORDER BY wo_id").fetchall()
    so_ids = [s[0] for s in bus]
    for i, r in enumerate(all_wos):
        so_id = so_ids[i % len(so_ids)]
        conn.execute("UPDATE work_orders SET sales_order_id = ? WHERE wo_id = ?", (so_id, r[0]))

    # --- Fix: Link downtime_log to equipment + inject varied failure histories ---
    # 1. Link existing downtime events to first equipment at each WC
    wc_equip = conn.execute(
        "SELECT work_center_id, MIN(equipment_id) AS eq_id FROM equipment WHERE work_center_id IS NOT NULL GROUP BY work_center_id"
    ).fetchall()
    wc_eq_map = {r[0]: r[1] for r in wc_equip if r[0] and r[1]}
    for wc_id, eq_id in wc_eq_map.items():
        conn.execute("UPDATE downtime_log SET equipment_id = ? WHERE wc_id = ? AND equipment_id IS NULL", (eq_id, wc_id))

    # 2. Inject varied failure histories per equipment type
    # Different equipment types have different MTBF profiles:
    #   Extruders: frequent failures (MTBF ~200 hrs) — high wear
    #   Braiders: moderate (MTBF ~400 hrs)
    #   Testing: rare failures (MTBF ~800 hrs) — electronic
    #   Draw/Strand: moderate-high (MTBF ~500 hrs)
    #   Compounding: very frequent (MTBF ~150 hrs) — Banbury mixer wear
    failure_profiles = {
        'COMPOUND-1': [(3,20),(8,35),(14,45),(20,25),(27,60),(33,30)],   # 6 failures, short intervals
        'COMPOUND-2': [(5,15),(12,40),(19,30),(28,50)],                   # 4 failures
        'DRAW-1':     [(4,25),(11,50),(22,30),(30,40),(38,20)],           # 5 failures
        'CV-1':       [(2,30),(7,45),(15,60),(25,35),(35,55),(42,25)],    # 6 failures, extruder wear
        'CV-2':       [(6,40),(16,55),(26,30),(36,45)],                   # 4 failures
        'CV-3':       [(3,50),(13,35),(28,40)],                           # 3 failures
        'PLCV-1':     [(5,60),(10,75),(18,45),(24,90),(32,50),(40,30)],   # 6 heavy failures
        'BRAID-1':    [(8,20),(20,30),(34,25)],                           # 3 failures
        'CABLE-1':    [(10,35),(25,45)],                                   # 2 failures
        'TEST-1':     [(15,15),(35,20)],                                   # 2 small failures
        'ARMOR-1':    [(7,55),(14,70),(23,40),(31,60),(39,45)],           # 5 failures
        'STRAND-1':   [(9,30),(21,40),(33,25)],                           # 3 failures
    }
    for wc_id, failures in failure_profiles.items():
        eq_id = wc_eq_map.get(wc_id)
        if not eq_id:
            continue
        for day_offset, duration in failures:
            ts = (base + timedelta(days=day_offset, hours=random.randint(6,18))).strftime("%Y-%m-%d %H:%M:%S")
            end_ts = (base + timedelta(days=day_offset, hours=random.randint(6,18), minutes=duration)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO downtime_log (wc_id, equipment_id, start_time, end_time, duration_min, category, cause, notes) VALUES (?,?,?,?,?,?,?,?)",
                (wc_id, eq_id, ts, end_ts, duration, 'Breakdown',
                 random.choice(['Motor failure','Bearing wear','Heater burnout','Sensor fault','Belt snap','Die crack','Gearbox issue']),
                 'Injected failure history for predictive maintenance'))

    # --- Realistic multi-tier lot genealogy ---
    # Build 8-tier chains: RAW → COMPOUND → WIRE → INSULATED → SHIELDED → CABLED → JACKETED → CUT/REEL
    # 5 product lines, each with full genealogy
    product_lines = [
        ("WO-2026-001", "INST-3C16-FBS", "A"),
        ("WO-2026-002", "CTRL-2C12-XA", "B"),
        ("WO-2026-003", "DHT-1C12-260", "C"),
        ("WO-2026-004", "UL2196-2C14", "U"),
        ("WO-2026-005", "IC-12AWG-XLPE", "I"),
    ]
    lot_id_counter = 100
    for wo_id, prod_id, fam in product_lines:
        pfx = fam + wo_id[-3:]  # e.g. A001, B002
        t = base + timedelta(days=random.randint(1, 10))

        # Tier 0: Raw materials
        raw_cu = f"RAW-CU-{pfx}"
        raw_comp = f"RAW-COMP-{pfx}"
        raw_shield = f"RAW-SHLD-{pfx}"

        # Tier 1: Compound batch (COMPOUND-1)
        cb = f"CB-{pfx}"
        for raw, qty in [(raw_cu, random.randint(200, 500)), (raw_comp, random.randint(100, 300))]:
            lot_id_counter += 1
            conn.execute(
                "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
                (cb, raw, wo_id, "T1-Compound", qty, (t + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")))

        # Tier 2: Drawn wire (DRAW-1)
        wire = f"WR-{pfx}"
        lot_id_counter += 1
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (wire, cb, wo_id, "T2-Drawing", random.randint(300, 600), (t + timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")))

        # Tier 3: Insulated conductor (CV-1/CV-2)
        insul = f"INS-{pfx}"
        lot_id_counter += 1
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (insul, wire, wo_id, "T3-Insulation", random.randint(200, 500), (t + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")))
        # Also consume compound for insulation
        lot_id_counter += 1
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (insul, cb, wo_id, "T3-Insulation", random.randint(50, 150), (t + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")))

        # Tier 4: Shielded (FOIL-1 or BRAID-1) — not all products have shields
        if fam in ("A", "B", "C"):
            shielded = f"SHL-{pfx}"
            lot_id_counter += 1
            conn.execute(
                "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
                (shielded, insul, wo_id, "T4-Shielding", random.randint(150, 400), (t + timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S")))
            conn.execute(
                "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
                (shielded, raw_shield, wo_id, "T4-Shielding", random.randint(20, 60), (t + timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S")))
            cable_input = shielded
        else:
            cable_input = insul

        # Tier 5: Cabled (CABLE-1) — multi-conductor assembly
        cabled = f"CBL-{pfx}"
        lot_id_counter += 1
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (cabled, cable_input, wo_id, "T5-Cabling", random.randint(100, 350), (t + timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S")))

        # Tier 6: Jacketed (PLCV-1)
        jacketed = f"JKT-{pfx}"
        lot_id_counter += 1
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (jacketed, cabled, wo_id, "T6-Jacketing", random.randint(100, 300), (t + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M:%S")))
        conn.execute(
            "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
            (jacketed, raw_comp, wo_id, "T6-Jacketing", random.randint(30, 80), (t + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M:%S")))

        # Tier 7: Cut to length + Reel (CUT-1)
        for reel_num in range(1, random.randint(3, 6)):
            reel_lot = f"RL-{pfx}-{reel_num:02d}"
            footage = random.randint(500, 5000)
            lot_id_counter += 1
            conn.execute(
                "INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
                (reel_lot, jacketed, wo_id, "T7-CutReel", footage, (t + timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")))
            # Link to reel_inventory
            reel_id = f"R-{pfx}-{reel_num:02d}"
            conn.execute(
                "INSERT OR IGNORE INTO reel_inventory (reel_id, lot_id, product_id, footage_ft, status, created_date) VALUES (?,?,?,?,?,?)",
                (reel_id, reel_lot, prod_id, footage, random.choice(["Full", "InUse", "Shipped"]),
                 (t + timedelta(hours=26)).strftime("%Y-%m-%d")))

    # Splice zone records (two input lots → one output)
    conn.execute("INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time) VALUES (?,?,?,?,?,?)",
                 ("INS-A001", "WR-B002", "WO-2026-001", "Splice", 15, (base + timedelta(hours=11)).strftime("%Y-%m-%d %H:%M:%S")))
    conn.execute("INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time,notes) VALUES (?,?,?,?,?,?,?)",
                 ("CBL-B002", "SHL-A001", "WO-2026-002", "Splice", 8, (base + timedelta(hours=19)).strftime("%Y-%m-%d %H:%M:%S"),
                  "Splice zone at footage mark 2,450 ft — two conductor payoffs joined"))

    # Regrind/reclaim record (scrap feeds back into compound)
    conn.execute("INSERT INTO lot_tracking (output_lot,input_lot,wo_id,tier_level,qty_consumed,transaction_time,notes) VALUES (?,?,?,?,?,?,?)",
                 ("CB-U004", "INS-A001", None, "Regrind", 25, (base + timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S"),
                  "PVC regrind: 25 lb scrap from INS-A001 blended into compound batch CB-U004 (8% regrind by weight per ASTM D2287)"))

    # --- Print marking records ---
    legends = {
        "A": "SodhiCable {pid} {awg}AWG {cond}/C {jkt} 600V UL TC-ER",
        "B": "SodhiCable {pid} {awg}AWG {cond}/C {jkt} ARMORED 600V",
        "C": "SodhiCable {pid} {awg}AWG DHT {jkt} 260C RATED",
        "U": "SodhiCable {pid} {awg}AWG {cond}/C UL2196 FIRE RATED 600V",
        "R": "SodhiCable {pid} {awg}AWG {jkt} 600V UL",
        "S": "SodhiCable {pid} {awg}AWG {cond}/C MIL-DTL-24643",
        "I": "SodhiCable {pid} {awg}AWG {jkt} 90C 600V",
        "M": "SodhiCable {pid} {awg} MV-105 {jkt} 15KV",
        "D": "SodhiCable {pid} DHT FLATPACK {jkt} 260C",
    }
    products = conn.execute("SELECT product_id, family, awg, conductors, jacket_type FROM products").fetchall()
    wo_ids = [r[0] for r in conn.execute("SELECT wo_id FROM work_orders WHERE status IN ('Complete','InProcess')").fetchall()]
    reel_ids = [r[0] for r in conn.execute("SELECT reel_id FROM reel_inventory LIMIT 30").fetchall()]

    for i in range(60):
        p = random.choice(products)
        pid, fam = p[0], p[1]
        legend = legends.get(fam, legends["R"]).format(pid=pid, awg=p[2] or "12", cond=p[3] or 1, jkt=p[4] or "PVC")
        t = base + timedelta(hours=i * 5, minutes=random.randint(0, 59))
        method = random.choice(["Inkjet", "Inkjet", "Inkjet", "Hot Stamp", "Laser"])
        color = "White" if fam in ("A", "B", "C", "D") else "Black" if fam in ("R", "I") else "Yellow"
        verified = random.random() < 0.85
        leg, adh, spc = int(random.random() < 0.95), int(random.random() < 0.97), int(random.random() < 0.93)
        status = "Pass" if verified and leg and adh and spc else "Fail" if verified else "Pending"
        conn.execute("""INSERT INTO print_marking (wo_id, reel_id, product_id, print_legend, print_method, color,
            character_height_mm, footage_interval_ft, voltage_rating, ul_listing,
            verification_status, verified_by, verified_date, legibility_pass, adhesion_pass, spacing_pass, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (random.choice(wo_ids) if wo_ids else None, reel_ids[i % len(reel_ids)] if reel_ids else None,
             pid, legend, method, color, random.choice([1.5, 2.0, 2.5, 3.0]), random.choice([0.5, 1.0, 2.0]),
             "600V" if fam in ("A","B","R","U","I") else "15KV" if fam=="M" else "N/A",
             "UL TC-ER" if fam in ("A","B") else "UL2196" if fam=="U" else "MIL-DTL" if fam=="S" else "UL",
             status, random.randint(6,7) if verified else None,
             t.strftime("%Y-%m-%d %H:%M:%S") if verified else None, leg, adh, spc,
             t.strftime("%Y-%m-%d %H:%M:%S")))

    # --- Expanded SPC, process data, labor, shifts, OEE ---
    # These are generated by seed_generator.py + post-seed script
    # Run the comprehensive seeding
    _seed_comprehensive(conn, base)

    # --- Energy Readings (kW draw per work center) ---
    energy_profiles = {
        'COMPOUND-1': (150, 25), 'COMPOUND-2': (130, 20),
        'DRAW-1': (35, 8),
        'STRAND-1': (25, 5),
        'CV-1': (95, 15), 'CV-2': (85, 12), 'CV-3': (100, 18),
        'FOIL-1': (15, 3), 'TAPE-1': (12, 2),
        'BRAID-1': (30, 5), 'BRAID-2': (28, 5), 'BRAID-3': (25, 4),
        'CABLE-1': (45, 8), 'CABLE-2': (40, 7),
        'PLCV-1': (110, 18), 'LPML-1': (90, 15), 'PX-1': (120, 20),
        'ARMOR-1': (55, 10), 'CCCW-1': (50, 9),
        'PT-1': (60, 10),
        'TEST-1': (10, 2), 'TEST-2': (8, 2),
        'CUT-1': (15, 3), 'PACK-1': (5, 1),
    }
    for wc_id, (mean_kw, sigma_kw) in energy_profiles.items():
        kwh_cum = 0
        for i in range(200):
            t = base + timedelta(hours=i * 1.68)
            kw = round(max(5, random.gauss(mean_kw, sigma_kw)), 1)
            kwh_cum += kw * 1.68  # kW * hours = kWh
            conn.execute(
                "INSERT INTO energy_readings (wc_id, kw_draw, kwh_cumulative, timestamp) VALUES (?,?,?,?)",
                (wc_id, kw, round(kwh_cum, 1), t.strftime("%Y-%m-%d %H:%M:%S"))
            )

    conn.commit()
    print(f"  OK: Extra seed data (print marking, reason codes, comprehensive data)")


def _seed_comprehensive(conn, base):
    """Seed comprehensive sensor, SPC, labor, OEE data for all lines."""
    random.seed(77)

    # Extrusion line sensor data
    lines = {
        "CV-1": {"Temperature_F": (365,3), "LineSpeed_fpm": (400,15), "InsulationOD_in": (0.065,0.001), "Tension_lbf": (25,2)},
        "CV-2": {"Temperature_F": (355,3.5), "LineSpeed_fpm": (3000,50), "InsulationOD_in": (0.048,0.0008), "Tension_lbf": (18,1.5)},
        "CV-3": {"Temperature_F": (370,4), "LineSpeed_fpm": (300,12), "InsulationOD_in": (0.072,0.0012), "Tension_lbf": (30,2.5)},
        "PLCV-1": {"Temperature_F": (370,3.5), "LineSpeed_fpm": (500,20), "JacketOD_in": (0.310,0.004), "Tension_lbf": (35,3)},
        "PX-1": {"Temperature_F": (590,4), "LineSpeed_fpm": (250,10), "FEP_OD_mil": (25.0,0.5), "Tension_lbf": (12,1)},
        "PT-1": {"Temperature_F": (420,5), "LineSpeed_fpm": (1000,30), "FiberOD_um": (125.0,1.0), "Tension_lbf": (2,0.3)},
        "LPML-1": {"Temperature_F": (340,3), "LineSpeed_fpm": (400,15), "JacketOD_in": (0.280,0.003), "Tension_lbf": (40,3.5)},
        "DRAW-1": {"Tension_lbf": (45,3), "LineSpeed_fpm": (800,25), "WireDiameter_in": (0.0253,0.0003)},
        "COMPOUND-1": {"BatchTemp_F": (280,8), "RotorSpeed_rpm": (40,2), "RamPressure_psi": (85,5), "PowerDraw_kW": (75,4)},
        "COMPOUND-2": {"BatchTemp_F": (275,6), "RotorSpeed_rpm": (38,1.5), "RamPressure_psi": (80,4), "PowerDraw_kW": (70,3)},
        "STRAND-1": {"Tension_lbf": (35,3), "LineSpeed_fpm": (600,20), "LayLength_in": (4.5,0.2)},
        "CABLE-1": {"LineSpeed_fpm": (350,12), "CableOD_in": (0.450,0.005)},
        "CABLE-2": {"LineSpeed_fpm": (300,10), "CableOD_in": (0.620,0.007)},
        "BRAID-1": {"LineSpeed_fpm": (200,8), "BraidCoverage_pct": (88.0,1.5)},
        "ARMOR-1": {"LineSpeed_fpm": (350,12), "ArmorOD_in": (0.520,0.006)},
        "CUT-1": {"LineSpeed_fpm": (1500,40), "CutLength_ft": (500,5)},
    }
    for wc_id, params in lines.items():
        for param, (mu, sigma) in params.items():
            for i in range(200):
                t = base + timedelta(hours=i * 1.68)
                drift = sigma * 1.5 if "Temperature" in param and wc_id == "CV-1" and 120 <= i <= 145 else 0
                val = round(random.gauss(mu + drift, sigma), 6 if sigma < 0.01 else 4 if sigma < 1 else 1)
                flag = "Bad" if abs(val-mu) > 3*sigma else "Suspect" if abs(val-mu) > 2*sigma else "Good"
                conn.execute("INSERT INTO process_data_live (wc_id, parameter, value, timestamp, quality_flag) VALUES (?,?,?,?,?)",
                             (wc_id, param, val, t.strftime("%Y-%m-%d %H:%M:%S"), flag))
            conn.execute("INSERT OR IGNORE INTO data_collection_points (wc_id, parameter_name, source_level, data_type, collection_freq, uom) VALUES (?,?,?,?,?,?)",
                         (wc_id, param, "PLC" if "Temp" in param else "Sensor", "Continuous", "1s" if "Temp" in param else "100ms", ""))

    # SPC readings for all extrusion OD/temp/speed
    A2, d2 = 0.577, 2.326
    spc_cfgs = [
        ("CV-1","InsulationOD_in",0.065,0.001,0.068,0.062,100,"WO-2026-002"),
        ("CV-2","InsulationOD_in",0.048,0.0008,0.050,0.046,100,"WO-2026-008"),
        ("CV-3","InsulationOD_in",0.072,0.0012,0.075,0.069,80,"WO-2026-011"),
        ("PLCV-1","JacketOD_in",0.310,0.004,0.320,0.300,100,"WO-2026-007"),
        ("PX-1","FEP_OD_mil",25.0,0.5,26.5,23.5,80,"WO-2026-005"),
        ("PT-1","FiberOD_um",125.0,1.0,127.0,123.0,80,"WO-2026-009"),
        ("LPML-1","JacketOD_in",0.280,0.003,0.290,0.270,80,"WO-2026-018"),
        ("CABLE-1","CableOD_in",0.450,0.005,0.462,0.438,80,"WO-2026-002"),
        ("CABLE-2","CableOD_in",0.620,0.007,0.635,0.605,60,"WO-2026-004"),
        ("DRAW-1","WireDiameter_in",0.0253,0.0003,0.0262,0.0244,120,"WO-2026-002"),
        ("DRAW-1","Tension_lbf",45.0,3.0,54.0,36.0,60,"WO-2026-002"),
        ("ARMOR-1","ArmorOD_in",0.520,0.006,0.535,0.505,60,"WO-2026-003"),
        ("CV-1","Temperature_F",365.0,3.0,375.0,355.0,80,"WO-2026-002"),
        ("CV-2","Temperature_F",355.0,3.5,365.0,345.0,80,"WO-2026-008"),
        ("PLCV-1","Temperature_F",370.0,3.5,380.0,360.0,80,"WO-2026-007"),
        ("PX-1","Temperature_F",590.0,4.0,600.0,580.0,60,"WO-2026-005"),
    ]
    for wc,param,mu,sig,usl,lsl,n,wo in spc_cfgs:
        for i in range(n):
            t = base + timedelta(hours=i*1.5)
            drift = sig*1.5 if wc=="CV-1" and "OD" in param and 60<=i<80 else sig*4 if wc=="PX-1" and "Temp" in param and i==40 else 0
            val = round(random.gauss(mu+drift, sig), 6 if sig<0.01 else 4 if sig<1 else 1)
            ucl = round(mu+A2*sig*d2, 6 if sig<0.01 else 4); lcl = round(mu-A2*sig*d2, 6 if sig<0.01 else 4)
            st = "OOC" if val>usl or val<lsl else "Warning" if val>ucl or val<lcl else "OK"
            rl = "Rule1_BeyondSpec" if st=="OOC" else "None"
            conn.execute("INSERT INTO spc_readings (wo_id,wc_id,measurement_date,parameter_name,measured_value,subgroup_id,usl,lsl,ucl,cl,lcl,rule_violation,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (wo,wc,t.strftime("%Y-%m-%d %H:%M:%S"),param,val,i//5+1,usl,lsl,ucl,mu,lcl,rl,st))

    # Shift schedules, labor time, certs, handoffs
    shifts = ["Day","Swing","Night"]
    personnel = conn.execute("SELECT person_id, shift, role FROM personnel WHERE active=1").fetchall()
    wcs_assign = ["DRAW-1","CV-1","CV-2","CABLE-1","PLCV-1","TEST-1","CUT-1","BRAID-1","COMPOUND-1"]
    for day in range(14):
        d = base + timedelta(days=day)
        for p in personnel:
            wc = wcs_assign[p[0] % len(wcs_assign)] if p[2] in ("Operator","Setup") else "TEST-1" if p[2]=="QA" else None
            conn.execute("INSERT INTO shift_schedule (person_id,shift_date,shift,wc_id) VALUES (?,?,?,?)", (p[0],d.strftime("%Y-%m-%d"),p[1],wc))
            hrs = round(random.uniform(6.5,8.5),1)
            ltype = random.choice(["Run","Run","Run","Run","Setup","Rework","Idle","PM"])
            conn.execute("INSERT INTO labor_time (person_id,clock_in,clock_out,hours,labor_type) VALUES (?,?,?,?,?)",
                         (p[0], (d+timedelta(hours=6 if p[1]=="Day" else 14 if p[1]=="Swing" else 22)).strftime("%Y-%m-%d %H:%M"),
                          (d+timedelta(hours=6 if p[1]=="Day" else 14 if p[1]=="Swing" else 22)+timedelta(hours=hrs)).strftime("%Y-%m-%d %H:%M"), hrs, ltype))

    # Cert expansions
    cert_map = {"DRAW-1":"Drawing","CV-1":"Extrusion","CV-2":"Extrusion","CABLE-1":"Cabling","BRAID-1":"Braiding","TEST-1":"Testing","CUT-1":"Cutting","COMPOUND-1":"Compounding","ARMOR-1":"Armoring"}
    existing = set((r[0],r[1]) for r in conn.execute("SELECT person_id,wc_id FROM personnel_certs").fetchall())
    for p in personnel:
        if p[2] in ("Operator","Setup"):
            for wc in random.sample(list(cert_map.keys()), min(3, len(cert_map))):
                if (p[0],wc) not in existing:
                    conn.execute("INSERT INTO personnel_certs (person_id,wc_id,certification_type,cert_level,issued_date,expiry_date,status) VALUES (?,?,?,?,?,?,?)",
                                 (p[0],wc,cert_map[wc],random.choice([1,2,2,3]),
                                  (base-timedelta(days=random.randint(180,720))).strftime("%Y-%m-%d"),
                                  (base+timedelta(days=random.randint(30,730))).strftime("%Y-%m-%d"),"Active"))
                    existing.add((p[0],wc))

    # Shift handoffs
    for day in range(14):
        d = base + timedelta(days=day)
        for fs, ts in [("Day","Swing"),("Swing","Night"),("Night","Day")]:
            machines = ",".join(random.sample(["CV-1","CV-2","DRAW-1","CABLE-1","PLCV-1","BRAID-1","TEST-1"], random.randint(3,6)))
            wos = ",".join(random.sample(["WO-2026-002","WO-2026-004","WO-2026-005","WO-2026-007","WO-2026-008"], random.randint(2,4)))
            qi = random.choice(["None","None","None","Diameter trending high on DRAW-1","Spark fault CV-2","Temperature excursion CV-1 zone 3"])
            sa = random.choice(["None","None","Cal due: TEST-1","Wet floor COMPOUND-1","None"])
            conn.execute("INSERT INTO shift_handoff (from_shift,to_shift,handoff_date,from_operator,to_operator,machines_running,wos_in_progress,quality_issues,safety_alerts,status) VALUES (?,?,?,?,?,?,?,?,?,'Acknowledged')",
                         (fs,ts,d.strftime("%Y-%m-%d"),f"EMP-{random.randint(1,12):03d}",f"EMP-{random.randint(13,30):03d}",machines,wos,qi,sa))

    # OEE shift reports for ALL work centers
    all_wcs = [r[0] for r in conn.execute("SELECT wc_id FROM work_centers WHERE wc_id != 'NJ-EXT'").fetchall()]
    # 5 days of shift reports (not 14) — keeps enough for trends but makes
    # new scenario-generated reports visibly impact the plant OEE average
    for day in range(5):
        d = base + timedelta(days=day)
        for wc in all_wcs:
            for shift in shifts:
                cap = conn.execute("SELECT capacity_ft_per_hr FROM work_centers WHERE wc_id=?", (wc,)).fetchone()
                c = (cap[0] or 500) if cap else 500
                a = round(random.uniform(0.78,0.96),3); p = round(random.uniform(0.78,0.95),3); q = round(random.uniform(0.94,0.99),3)
                oee = round(a*p*q,3); out=int(c*8*a*p); scr=int(out*(1-q)); dt_min=int((1-a)*480)
                conn.execute("INSERT INTO shift_reports (shift_date,shift_code,wc_id,oee_availability,oee_performance,oee_quality,oee_overall,total_output_ft,total_scrap_ft,total_downtime_min) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (d.strftime("%Y-%m-%d"),shift,wc,a,p,q,oee,out,scr,dt_min))


def _seed_erp_data(conn, base):
    """Seed Level 4 ERP data: POs, invoices, shipments, forecasts, ISA-95 messages, financials.
    Designed for demo-readiness: every OTC stage populated, multi-period P&L, deficit materials."""
    random.seed(99)
    import math
    carriers = ["FedEx Freight", "UPS Freight", "YRC", "Old Dominion"]

    # --- Historical Purchase Orders (10 closed + 5 open) ---
    materials = conn.execute("SELECT material_id, name, unit_cost, supplier FROM materials").fetchall()
    for i in range(10):
        mat = materials[i % len(materials)]
        po_id = f"PO-2026-{i+1:03d}"
        qty = random.randint(50, 500)
        order_dt = (base - timedelta(days=random.randint(20, 60))).strftime("%Y-%m-%d")
        expect_dt = (base - timedelta(days=random.randint(5, 19))).strftime("%Y-%m-%d")
        actual_dt = (base - timedelta(days=random.randint(1, 18))).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO purchase_orders (po_id,supplier,material_id,quantity,unit_cost,total_cost,order_date,expected_delivery,actual_delivery,status,created_by,approved_by,approved_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (po_id, mat[3], mat[0], qty, mat[2], round(qty * mat[2], 2),
             order_dt, expect_dt, actual_dt, "Closed", "ERP_SIM", "Purchasing_Mgr", order_dt))
        accepted = int(qty * random.uniform(0.97, 1.0))
        conn.execute(
            "INSERT INTO goods_receipts (po_id,material_id,qty_received,qty_accepted,qty_rejected,receipt_date,inspector,inspection_result,lot_number) VALUES (?,?,?,?,?,?,?,?,?)",
            (po_id, mat[0], qty, accepted, qty - accepted, actual_dt,
             f"QA-{random.randint(1,5)}", "Pass", f"GR-LOT-{random.randint(1000,9999)}"))

    for i in range(5):
        mat = materials[(10 + i) % len(materials)]
        po_id = f"PO-2026-{11+i:03d}"
        qty = random.randint(100, 400)
        status = ["Draft", "Approved", "Approved", "Sent", "Sent"][i]
        conn.execute(
            "INSERT INTO purchase_orders (po_id,supplier,material_id,quantity,unit_cost,total_cost,order_date,expected_delivery,status,created_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (po_id, mat[3], mat[0], qty, mat[2], round(qty * mat[2], 2),
             (base - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
             (base + timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d"), status, "ERP_SIM"))

    # --- OTC Pipeline: 20 dedicated ERP sales orders across ALL stages ---
    cust_ids = [r[0] for r in conn.execute("SELECT customer_id FROM customers").fetchall()]
    products = conn.execute("SELECT product_id, revenue_per_kft, cost_per_kft FROM products LIMIT 20").fetchall()

    # Stage distribution: 3 Order Received, 3 In Production, 4 Produced, 4 Shipped, 3 Invoiced, 3 Paid
    otc_stages = (["order_received"] * 3 + ["in_production"] * 3 + ["produced"] * 4 +
                  ["shipped"] * 4 + ["invoiced"] * 3 + ["paid"] * 3)

    for i, stage in enumerate(otc_stages):
        so_id = f"SO-ERP-DEMO-{i+1:03d}"
        cust = cust_ids[i % len(cust_ids)]
        prod = products[i % len(products)]
        qty = round(random.uniform(2, 12), 1)
        rev_kft = prod[1] or 50
        cost_kft = prod[2] or 30
        due = (base + timedelta(days=random.randint(-5, 20))).strftime("%Y-%m-%d")
        order_dt = (base - timedelta(days=random.randint(10, 30))).strftime("%Y-%m-%d")
        bu = ["Defense", "Industrial", "Infrastructure", "Oil & Gas"][i % 4]

        # Create SO
        so_status = "Open" if stage == "order_received" else "InProgress" if stage == "in_production" else "Shipped"
        conn.execute("INSERT OR IGNORE INTO sales_orders (sales_order_id,customer_id,order_date,required_date,priority,status,business_unit) VALUES (?,?,?,?,?,?,?)",
                     (so_id, cust, order_dt, due, random.randint(1, 5), so_status, bu))
        conn.execute("INSERT INTO sales_order_lines (sales_order_id,product_id,quantity,unit_price,promised_date) VALUES (?,?,?,?,?)",
                     (so_id, prod[0], qty, rev_kft, due))

        # Create WO if past "order_received"
        if stage != "order_received":
            wo_id = f"WO-ERP-DEMO-{i+1:04d}"
            wo_status = "Released" if stage == "in_production" else "Complete"
            a_start = (base - timedelta(days=random.randint(3, 15))).strftime("%Y-%m-%d")
            a_end = (base - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d") if wo_status == "Complete" else None
            conn.execute(
                "INSERT INTO work_orders (wo_id,product_id,order_qty_kft,priority,due_date,status,created_date,actual_start,actual_end,sales_order_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (wo_id, prod[0], qty, 3, due, wo_status, order_dt, a_start, a_end, so_id))

        # Create shipment if past "produced"
        if stage in ("shipped", "invoiced", "paid"):
            ship_id = f"SHIP-DEMO-{i+1:03d}"
            conn.execute("INSERT INTO shipments (shipment_id,sales_order_id,wo_id,customer_id,ship_date,carrier,qty_shipped,status) VALUES (?,?,?,?,?,?,?,?)",
                         (ship_id, so_id, wo_id, cust, (base - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
                          random.choice(carriers), qty, "Delivered"))

        # Create invoice if past "shipped"
        if stage in ("invoiced", "paid"):
            inv_id = f"INV-DEMO-{i+1:03d}"
            subtotal = round(qty * rev_kft, 2)
            tax = round(subtotal * 0.07, 2)
            inv_status = "Paid" if stage == "paid" else random.choice(["Sent", "Sent", "Overdue"])
            pay_dt = (base - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d") if stage == "paid" else None
            conn.execute(
                "INSERT INTO invoices (invoice_id,sales_order_id,customer_id,invoice_date,due_date,subtotal,tax,total,status,payment_date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (inv_id, so_id, cust, (base - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
                 (base + timedelta(days=30)).strftime("%Y-%m-%d"), subtotal, tax, round(subtotal + tax, 2), inv_status, pay_dt))

    # --- Financial Ledger: 3-month spread (Feb, Mar, Apr) ---
    completed_wos = conn.execute("""
        SELECT wo.wo_id, wo.order_qty_kft, p.revenue_per_kft, p.cost_per_kft, wo.actual_end
        FROM work_orders wo JOIN products p ON wo.product_id = p.product_id
        WHERE wo.status = 'Complete' AND wo.actual_end IS NOT NULL
        LIMIT 40
    """).fetchall()
    months = ["2026-02", "2026-03", "2026-04"]
    for i, wo in enumerate(completed_wos):
        wo_id, qty, rev, cost = wo[0], wo[1] or 1, wo[2] or 50, wo[3] or 30
        period = months[i % 3]
        entry_date = f"{period}-{random.randint(1,28):02d}"
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "Revenue", "WO", wo_id, round(qty * rev, 2), f"Revenue: {wo_id}", period))
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "COGS", "WO", wo_id, round(qty * cost, 2), f"COGS: {wo_id}", period))

    # Material, labor, overhead, scrap costs per month
    for period in months:
        entry_date = f"{period}-15"
        # Material costs from POs
        mat_cost = round(random.uniform(15000, 35000), 2)
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "MaterialCost", "PO", "MONTHLY", mat_cost, f"Material purchases: {period}", period))
        # Labor
        labor = round(34 * 8 * 22 * 28.50 / 3, 2)  # ~$57K/month
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "LaborCost", "WC", "ALL", labor, f"Labor cost: {period}", period))
        # Overhead (~15% of revenue for that period)
        rev_total = sum(qty * (rev or 50) for _, qty, rev, _, _ in completed_wos[len(months):] if qty) / 3
        overhead = round(rev_total * 0.15, 2) if rev_total > 0 else 8000
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "OverheadCost", "WC", "ALL", overhead, f"Overhead: {period}", period))
        # Scrap
        scrap_cost = round(random.uniform(500, 2500), 2)
        conn.execute("INSERT INTO financial_ledger (entry_date,account_type,reference_type,reference_id,amount,description,period) VALUES (?,?,?,?,?,?,?)",
                     (entry_date, "ScrapCost", "WC", "ALL", scrap_cost, f"Scrap cost: {period}", period))

    # --- Force inventory deficits for demo variety ---
    conn.execute("UPDATE inventory SET qty_on_hand = 5, qty_allocated = 4 WHERE material_id = 'MAT-001'")
    conn.execute("UPDATE inventory SET qty_on_hand = 0, qty_allocated = 0 WHERE material_id = 'MAT-006'")
    conn.execute("UPDATE inventory SET qty_on_hand = 8, qty_allocated = 7 WHERE material_id = 'MAT-008'")
    conn.execute("UPDATE inventory SET qty_on_hand = 3, qty_allocated = 2 WHERE material_id = 'MAT-011'")

    # --- Demand Forecast (8 weeks history per family) ---
    families = [r[0] for r in conn.execute("SELECT DISTINCT family FROM products").fetchall()]
    family_base_demand = {"A": 12, "B": 8, "C": 5, "D": 3, "I": 20, "M": 4, "R": 25, "S": 6, "U": 10}
    import math
    for fam in families:
        base_d = family_base_demand.get(fam, 10)
        forecast = base_d  # initial forecast
        for w in range(8):
            period_start = (base - timedelta(weeks=8 - w)).strftime("%Y-%m-%d")
            seasonal = 1 + 0.25 * math.sin(2 * math.pi * w / 52)
            actual = round(base_d * seasonal * random.uniform(0.7, 1.3), 1)
            forecast = round(0.3 * actual + 0.7 * forecast, 1)  # SES
            conn.execute("INSERT INTO demand_forecast (product_family,period_start,period_type,forecast_qty,actual_qty,forecast_method,alpha) VALUES (?,?,?,?,?,?,?)",
                         (fam, period_start, "week", forecast, actual, "SES", 0.3))

    # --- S&OP Plan (current month, 12-week horizon) ---
    for fam in families:
        base_d = family_base_demand.get(fam, 10)
        beg_inv = random.randint(10, 50)
        for w in range(12):
            period_start = (base + timedelta(weeks=w)).strftime("%Y-%m-%d")
            demand = round(base_d * random.uniform(0.8, 1.2), 1)
            prod_plan = round(demand * 1.1, 1)  # plan 10% above forecast
            end_inv = round(beg_inv + prod_plan - demand, 1)
            cap_req = round(prod_plan * 2.5, 1)  # ~2.5 hrs per KFT
            cap_avail = round(40 * 3, 1)  # 3 shifts * 40 hrs
            gap = round(cap_avail - cap_req, 1)
            conn.execute("INSERT INTO sop_plan (plan_version,product_family,period_start,demand_forecast,production_plan,beginning_inventory,ending_inventory,capacity_required_hrs,capacity_available_hrs,capacity_gap,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (1, fam, period_start, demand, prod_plan, beg_inv, end_inv, cap_req, cap_avail, gap, "Draft"))
            beg_inv = end_inv

    # --- ISA-95 Messages (historical) ---
    msg_types_l4_l3 = [
        ("ProductionSchedule", "WO released to MES"),
        ("MaterialRequirement", "Material order placed"),
        ("ResourceRequirement", "Capacity plan update"),
    ]
    msg_types_l3_l4 = [
        ("ProductionPerformance", "WO completed"),
        ("MaterialReceipt", "Goods received"),
        ("QualityReport", "NCR created"),
        ("InventoryCount", "Inventory adjusted"),
    ]
    for i in range(30):
        t = (base - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        if random.random() < 0.45:
            mtype, summary = random.choice(msg_types_l4_l3)
            direction, src, tgt = "L4_to_L3", "ERP", "MES"
            ref = f"WO-2026-{random.randint(1,100):03d}" if "Production" in mtype else f"PO-2026-{random.randint(1,15):03d}"
        else:
            mtype, summary = random.choice(msg_types_l3_l4)
            direction, src, tgt = "L3_to_L4", "MES", "ERP"
            ref = f"WO-2026-{random.randint(1,100):03d}" if "Production" in mtype else f"NCR-{random.randint(1,5)}" if "Quality" in mtype else f"MAT-{random.randint(1,16):03d}"
        conn.execute("INSERT INTO isa95_messages (timestamp,direction,message_type,source_system,target_system,payload_summary,reference_id,status,processing_time_ms) VALUES (?,?,?,?,?,?,?,?,?)",
                     (t, direction, mtype, src, tgt, f"{summary}: {ref}", ref, random.choice(["Processed","Processed","Processed","Acknowledged"]), random.randint(10, 500)))

    # --- ERP Sim State (initial) ---
    conn.execute("INSERT OR REPLACE INTO erp_sim_state (key,value) VALUES ('sim_week','17')")
    conn.execute("INSERT OR REPLACE INTO erp_sim_state (key,value) VALUES ('sim_date',?)", (base.strftime("%Y-%m-%d"),))
    conn.execute("INSERT OR REPLACE INTO erp_sim_state (key,value) VALUES ('total_orders_generated','15')")
    conn.execute("INSERT OR REPLACE INTO erp_sim_state (key,value) VALUES ('total_pos_created','15')")

    conn.commit()
    print(f"  OK: ERP seed data (POs, invoices, shipments, forecasts, ISA-95 messages, financials)")


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old database")

    # Also remove generated SQL to force regeneration
    gen_path = os.path.join(DB_DIR, "seed_data_generated.sql")
    if os.path.exists(gen_path):
        os.remove(gen_path)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    print("Creating SodhiCable MES database...")

    execute_sql_file(conn, os.path.join(DB_DIR, "schema.sql"), "schema.sql")
    execute_sql_file(conn, os.path.join(DB_DIR, "seed_data.sql"), "seed_data.sql")

    # Generated seed data (SPC drift, spark tests, downtime, etc.)
    if not os.path.exists(gen_path):
        sys.path.insert(0, DB_DIR)
        from seed_generator import generate_all
        sql = generate_all()
        with open(gen_path, "w") as f:
            f.write(sql)
        print(f"  OK: Generated seed_data_generated.sql")
    execute_sql_file(conn, gen_path, "seed_data_generated.sql")

    execute_sql_file(conn, os.path.join(DB_DIR, "views.sql"), "views.sql")

    # Migrations — set up tracking table and mark baseline migrations as applied
    from migrate import ensure_migrations_table
    ensure_migrations_table(conn)
    try:
        conn.execute("ALTER TABLE scrap_log ADD COLUMN disposition TEXT DEFAULT 'Scrap'")
        print("  OK: Added disposition column to scrap_log")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.execute("INSERT OR IGNORE INTO _migrations (migration_id) VALUES ('001_add_disposition_to_scrap_log.sql')")
    conn.commit()
    print("  OK: Migration tracking initialized")

    # Extra comprehensive data
    seed_extra_data(conn)

    # Level 4 ERP data
    _seed_erp_data(conn, datetime(2026, 4, 1))

    # Verify
    tc = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    vc = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view'").fetchone()[0]
    total_rows = 0
    for t in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            total_rows += cnt
            if cnt > 0:
                print(f"    {t}: {cnt:,}")
        except:
            pass

    conn.close()
    print(f"\n  {tc} tables, {vc} views, {total_rows:,} total rows")
    print("Done!")


if __name__ == "__main__":
    main()
