-- SodhiCable MES v4.0 — Schema (60 tables, snake_case matching scheduling engine)
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (product_id TEXT PRIMARY KEY, name TEXT NOT NULL, family TEXT NOT NULL, description TEXT, conductors INTEGER, awg TEXT, shield_type TEXT, jacket_type TEXT, armor_type TEXT, primary_bu TEXT, production_tier TEXT, revenue_per_kft REAL NOT NULL, cost_per_kft REAL NOT NULL, max_order_qty_kft REAL NOT NULL, uom TEXT DEFAULT 'KFT', notes TEXT);
CREATE TABLE IF NOT EXISTS work_centers (wc_id TEXT PRIMARY KEY, name TEXT NOT NULL, wc_type TEXT NOT NULL, num_parallel INTEGER DEFAULT 1, capacity_hrs_per_week REAL NOT NULL, capacity_ft_per_hr REAL, utilization_target REAL DEFAULT 0.80, setup_time_min REAL DEFAULT 30.0, cost_per_hr REAL DEFAULT 85.0, manning REAL DEFAULT 1.0, isa_level INTEGER DEFAULT 3, notes TEXT);
CREATE TABLE IF NOT EXISTS materials (material_id TEXT PRIMARY KEY, name TEXT NOT NULL, material_type TEXT NOT NULL, uom TEXT NOT NULL, unit_cost REAL NOT NULL, lead_time_days INTEGER NOT NULL, safety_stock_qty REAL DEFAULT 0, supplier TEXT, tier TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, business_unit TEXT NOT NULL, contract_type TEXT, quality_level TEXT, address TEXT, contact TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS plants (plant_id TEXT PRIMARY KEY, plant_name TEXT NOT NULL, location TEXT, capacity_kft REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reel_types (reel_type_id TEXT PRIMARY KEY, name TEXT NOT NULL, max_footage_ft REAL NOT NULL, material TEXT, tare_weight_lb REAL);
CREATE TABLE IF NOT EXISTS unit_conversions (from_uom TEXT NOT NULL, to_uom TEXT NOT NULL, factor REAL NOT NULL, PRIMARY KEY (from_uom, to_uom));

-- F1
CREATE TABLE IF NOT EXISTS work_orders (wo_id TEXT PRIMARY KEY, sales_order_id TEXT, product_id TEXT NOT NULL REFERENCES products(product_id), business_unit TEXT, order_qty_kft REAL NOT NULL, priority INTEGER DEFAULT 5, due_date TEXT, planned_start TEXT, planned_end TEXT, actual_start TEXT, actual_end TEXT, created_date TEXT DEFAULT (datetime('now')), status TEXT DEFAULT 'Pending', triggered_by_wo TEXT, weight REAL, notes TEXT);
CREATE TABLE IF NOT EXISTS routings (routing_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL REFERENCES products(product_id), sequence_num INTEGER NOT NULL, wc_id TEXT NOT NULL REFERENCES work_centers(wc_id), operation_name TEXT, process_time_min_per_100ft REAL NOT NULL, setup_time_min REAL DEFAULT 0, notes TEXT, UNIQUE(product_id, sequence_num));
CREATE TABLE IF NOT EXISTS operations (operation_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT NOT NULL, routing_id INTEGER, step_sequence INTEGER NOT NULL, wc_id TEXT NOT NULL, operation_name TEXT, planned_start TEXT, planned_end TEXT, actual_start TEXT, actual_end TEXT, setup_time_min REAL DEFAULT 0, run_time_min REAL DEFAULT 0, status TEXT DEFAULT 'Pending', assigned_to INTEGER, equipment_id INTEGER, qty_good REAL DEFAULT 0, qty_scrap REAL DEFAULT 0, notes TEXT);

-- F2
CREATE TABLE IF NOT EXISTS changeover_matrix (from_product TEXT NOT NULL, to_product TEXT NOT NULL, setup_minutes REAL NOT NULL, scrap_ft REAL DEFAULT 0, compound_change INTEGER DEFAULT 0, PRIMARY KEY (from_product, to_product));
CREATE TABLE IF NOT EXISTS schedule (schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT NOT NULL, wc_id TEXT NOT NULL, sequence_pos INTEGER, planned_start TEXT, planned_end TEXT, setup_minutes REAL DEFAULT 0, status TEXT DEFAULT 'Planned');
CREATE TABLE IF NOT EXISTS scheduler_config (config_id INTEGER PRIMARY KEY AUTOINCREMENT, wc_id TEXT, algorithm TEXT, objective_func TEXT, parameters TEXT, is_default INTEGER DEFAULT 0, notes TEXT);
CREATE TABLE IF NOT EXISTS schedule_results (result_id INTEGER PRIMARY KEY AUTOINCREMENT, run_datetime TEXT DEFAULT (datetime('now')), algorithm TEXT NOT NULL, objective_func TEXT, objective_value REAL, num_jobs INTEGER, schedule_json TEXT, solve_time_sec REAL, optimality_gap REAL, notes TEXT);

-- F3
CREATE TABLE IF NOT EXISTS dispatch_queue (queue_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT NOT NULL, wc_id TEXT NOT NULL, priority_score REAL, queue_position INTEGER, enqueued_at TEXT DEFAULT (datetime('now')), status TEXT DEFAULT 'Waiting');
CREATE TABLE IF NOT EXISTS dispatch_log (log_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT NOT NULL, wc_id TEXT NOT NULL, operator_id INTEGER, dispatch_time TEXT DEFAULT (datetime('now')), completion_time TEXT, priority_score REAL, notes TEXT);

-- F4
CREATE TABLE IF NOT EXISTS recipes (recipe_id INTEGER PRIMARY KEY AUTOINCREMENT, recipe_code TEXT UNIQUE, description TEXT, product_id TEXT, work_center_id TEXT, tm_number TEXT, tm_revision TEXT, version INTEGER DEFAULT 1, status TEXT DEFAULT 'Draft', approved_by TEXT, effective_date TEXT, superseded_date TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS recipe_parameters (param_id INTEGER PRIMARY KEY AUTOINCREMENT, recipe_id INTEGER NOT NULL, parameter_name TEXT NOT NULL, parameter_value REAL, uom TEXT, lower_limit REAL, upper_limit REAL, control_type TEXT DEFAULT 'SPC');
CREATE TABLE IF NOT EXISTS recipe_ingredients (ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT, recipe_id INTEGER NOT NULL, material_id TEXT, qty_per_kft REAL NOT NULL, uom TEXT, scrap_allowance REAL DEFAULT 0.02);
CREATE TABLE IF NOT EXISTS documents (doc_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, doc_type TEXT NOT NULL, doc_name TEXT NOT NULL, file_path TEXT, created_date TEXT DEFAULT (datetime('now')), version TEXT DEFAULT '1.0', revision TEXT, effective_date TEXT, supersedes_doc_id INTEGER, status TEXT DEFAULT 'Draft', notes TEXT);
CREATE TABLE IF NOT EXISTS document_links (link_id INTEGER PRIMARY KEY AUTOINCREMENT, doc_id INTEGER NOT NULL, linked_entity_type TEXT NOT NULL, linked_entity_id TEXT NOT NULL, link_type TEXT DEFAULT 'References');

-- F5
CREATE TABLE IF NOT EXISTS process_data_live (reading_id INTEGER PRIMARY KEY AUTOINCREMENT, wc_id TEXT NOT NULL, parameter TEXT NOT NULL, value REAL NOT NULL, timestamp TEXT DEFAULT (datetime('now')), quality_flag TEXT DEFAULT 'Good', notes TEXT);
CREATE TABLE IF NOT EXISTS spark_test_log (log_id INTEGER PRIMARY KEY AUTOINCREMENT, reel_id TEXT, wo_id TEXT, wc_id TEXT, footage_at_fault_ft REAL, voltage_kv REAL, result TEXT NOT NULL, timestamp TEXT DEFAULT (datetime('now')), notes TEXT);
CREATE TABLE IF NOT EXISTS events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, wc_id TEXT, event_type TEXT NOT NULL, event_time TEXT DEFAULT (datetime('now')), operator_id INTEGER, details TEXT);
CREATE TABLE IF NOT EXISTS data_collection_points (point_id INTEGER PRIMARY KEY AUTOINCREMENT, wc_id TEXT NOT NULL, parameter_name TEXT NOT NULL, source_level TEXT, data_type TEXT, collection_freq TEXT, uom TEXT, notes TEXT);

-- F6
CREATE TABLE IF NOT EXISTS personnel (person_id INTEGER PRIMARY KEY AUTOINCREMENT, employee_code TEXT UNIQUE NOT NULL, employee_name TEXT NOT NULL, department TEXT, job_title TEXT, role TEXT DEFAULT 'Operator', shift TEXT DEFAULT 'Day', certification_level INTEGER DEFAULT 1, hire_date TEXT, active INTEGER DEFAULT 1, notes TEXT);
CREATE TABLE IF NOT EXISTS personnel_certs (cert_id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL, wc_id TEXT, certification_type TEXT NOT NULL, cert_level INTEGER DEFAULT 1, issued_date TEXT, expiry_date TEXT, certified_by TEXT, status TEXT DEFAULT 'Active', notes TEXT);
CREATE TABLE IF NOT EXISTS shift_handoff (handoff_id INTEGER PRIMARY KEY AUTOINCREMENT, from_shift TEXT NOT NULL, to_shift TEXT NOT NULL, handoff_date TEXT NOT NULL, from_operator TEXT, to_operator TEXT, machines_running TEXT, wos_in_progress TEXT, quality_issues TEXT, safety_alerts TEXT, notes TEXT, status TEXT DEFAULT 'Pending');
CREATE TABLE IF NOT EXISTS shift_schedule (schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL, shift_date TEXT NOT NULL, shift TEXT NOT NULL, wc_id TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS labor_time (labor_id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id INTEGER, person_id INTEGER NOT NULL, clock_in TEXT, clock_out TEXT, hours REAL, labor_type TEXT DEFAULT 'Run', notes TEXT);

-- F7
CREATE TABLE IF NOT EXISTS spc_readings (spc_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, wc_id TEXT NOT NULL, operation_id INTEGER, measurement_date TEXT DEFAULT (datetime('now')), parameter_name TEXT NOT NULL, measured_value REAL NOT NULL, subgroup_id INTEGER, usl REAL, lsl REAL, ucl REAL, cl REAL, lcl REAL, rule_violation TEXT DEFAULT 'None', status TEXT DEFAULT 'OK', notes TEXT);
CREATE TABLE IF NOT EXISTS ncr (ncr_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT, wo_id TEXT, lot_number TEXT, defect_type TEXT, description TEXT, severity TEXT DEFAULT 'Minor', detected_at TEXT, detected_by INTEGER, reported_date TEXT DEFAULT (datetime('now')), root_cause TEXT, corrective_action TEXT, preventive_action TEXT, resolution TEXT, resolved_date TEXT, closed_by INTEGER, status TEXT DEFAULT 'Open');
CREATE TABLE IF NOT EXISTS test_results (test_id INTEGER PRIMARY KEY AUTOINCREMENT, lot_number TEXT, wo_id TEXT, operation_id INTEGER, product_id TEXT, test_type TEXT NOT NULL, test_spec TEXT, test_value REAL, test_uom TEXT, lower_limit REAL, upper_limit REAL, pass_fail TEXT, test_date TEXT DEFAULT (datetime('now')), tester_id INTEGER, equipment_id INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS test_protocols (protocol_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, test_sequence INTEGER, test_type TEXT NOT NULL, spec_reference TEXT, frequency TEXT, pass_criteria TEXT, fail_action TEXT DEFAULT 'Hold', notes TEXT);

-- F8
CREATE TABLE IF NOT EXISTS hold_release (hold_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, lot_number TEXT, hold_reason TEXT, held_date TEXT DEFAULT (datetime('now')), held_by INTEGER, disposition TEXT, disposition_by INTEGER, disposition_datetime TEXT, released_date TEXT, related_ncr INTEGER, hold_status TEXT DEFAULT 'Active', notes TEXT);
CREATE TABLE IF NOT EXISTS process_deviations (deviation_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, wc_id TEXT, parameter_name TEXT, detection_method TEXT, deviation_value REAL, setpoint_value REAL, severity TEXT DEFAULT 'Warning', timestamp TEXT DEFAULT (datetime('now')), corrective_action TEXT, resolved INTEGER DEFAULT 0, notes TEXT);
CREATE TABLE IF NOT EXISTS recipe_download_log (download_id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id INTEGER, recipe_id INTEGER NOT NULL, download_datetime TEXT DEFAULT (datetime('now')), acknowledged_by INTEGER, acknowledged_at TEXT, notes TEXT);

-- F9
CREATE TABLE IF NOT EXISTS equipment (equipment_id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_code TEXT UNIQUE NOT NULL, description TEXT, work_center_id TEXT, equipment_type TEXT, manufacturer TEXT, model TEXT, serial_number TEXT, install_date TEXT, last_pm_date TEXT, next_pm_date TEXT, calibration_due TEXT, calibration_freq_days INTEGER, status TEXT DEFAULT 'Active', notes TEXT);
CREATE TABLE IF NOT EXISTS maintenance (maint_id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER, wc_id TEXT, maint_type TEXT NOT NULL, scheduled_date TEXT, completed_date TEXT, duration_hours REAL, technician TEXT, performed_by INTEGER, result TEXT, status TEXT DEFAULT 'Pending', notes TEXT);
CREATE TABLE IF NOT EXISTS maintenance_schedule (schedule_id INTEGER PRIMARY KEY AUTOINCREMENT, equipment_id INTEGER NOT NULL, pm_type TEXT, frequency_days INTEGER, last_performed TEXT, next_due TEXT, assigned_to INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS downtime_log (log_id INTEGER PRIMARY KEY AUTOINCREMENT, wc_id TEXT NOT NULL, equipment_id INTEGER, start_time TEXT NOT NULL, end_time TEXT, duration_min REAL, category TEXT NOT NULL, cause TEXT, operator_id INTEGER, notes TEXT, created_at TEXT DEFAULT (datetime('now')));

-- F10
CREATE TABLE IF NOT EXISTS lot_tracking (lot_id INTEGER PRIMARY KEY AUTOINCREMENT, output_lot TEXT NOT NULL, input_lot TEXT, input_material_id TEXT, input_product_id TEXT, wo_id TEXT, operation_id INTEGER, qty_consumed REAL, uom TEXT, tier_level TEXT, transaction_time TEXT DEFAULT (datetime('now')), notes TEXT);
CREATE TABLE IF NOT EXISTS reel_inventory (reel_id TEXT PRIMARY KEY, reel_type_id TEXT, wo_id TEXT, lot_id TEXT, product_id TEXT, footage_ft REAL DEFAULT 0, status TEXT DEFAULT 'Empty', created_date TEXT DEFAULT (datetime('now')), created_by TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS inventory (inv_id INTEGER PRIMARY KEY AUTOINCREMENT, material_id TEXT, product_id TEXT, location_code TEXT, lot_number TEXT, qty_on_hand REAL DEFAULT 0, qty_allocated REAL DEFAULT 0, uom TEXT, receipt_date TEXT, expiration_date TEXT, fifo_date TEXT, status TEXT DEFAULT 'Available', notes TEXT);

-- F11
CREATE TABLE IF NOT EXISTS kpis (kpi_id INTEGER PRIMARY KEY AUTOINCREMENT, kpi_name TEXT NOT NULL, kpi_value REAL, target_value REAL, measurement_date TEXT DEFAULT (datetime('now')), unit TEXT, wc_id TEXT, period_start TEXT, period_end TEXT, status TEXT DEFAULT 'Tracking');
CREATE TABLE IF NOT EXISTS scrap_log (scrap_id INTEGER PRIMARY KEY AUTOINCREMENT, wo_id TEXT, operation_id INTEGER, wc_id TEXT, cause_code TEXT NOT NULL, quantity_ft REAL NOT NULL, cost REAL, disposition TEXT, timestamp TEXT DEFAULT (datetime('now')), notes TEXT);
CREATE TABLE IF NOT EXISTS shift_reports (report_id INTEGER PRIMARY KEY AUTOINCREMENT, shift_date TEXT NOT NULL, shift_code TEXT NOT NULL, wc_id TEXT, oee_availability REAL, oee_performance REAL, oee_quality REAL, oee_overall REAL, total_output_ft REAL DEFAULT 0, total_scrap_ft REAL DEFAULT 0, total_downtime_min REAL DEFAULT 0, supervisor_id INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS kpi_definitions (kpi_def_id INTEGER PRIMARY KEY AUTOINCREMENT, kpi_name TEXT NOT NULL UNIQUE, formula TEXT, uom TEXT, target REAL, frequency TEXT, category TEXT, notes TEXT);

-- Sales / BOM / Buffer
CREATE TABLE IF NOT EXISTS sales_orders (sales_order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, order_date TEXT, required_date TEXT, priority INTEGER DEFAULT 5, status TEXT DEFAULT 'Open', business_unit TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS sales_order_lines (line_id INTEGER PRIMARY KEY AUTOINCREMENT, sales_order_id TEXT NOT NULL, product_id TEXT NOT NULL, quantity REAL NOT NULL, uom TEXT DEFAULT 'KFT', unit_price REAL, promised_date TEXT, status TEXT DEFAULT 'Open');
CREATE TABLE IF NOT EXISTS bom_products (bom_id INTEGER PRIMARY KEY AUTOINCREMENT, parent_product_id TEXT NOT NULL, child_product_id TEXT NOT NULL, qty_per REAL NOT NULL, uom TEXT, bom_level INTEGER DEFAULT 1, notes TEXT);
CREATE TABLE IF NOT EXISTS bom_materials (bom_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, material_id TEXT NOT NULL, qty_per_kft REAL NOT NULL, uom TEXT, bom_level INTEGER DEFAULT 1, scrap_factor REAL DEFAULT 0.02, notes TEXT);
CREATE TABLE IF NOT EXISTS buffer_inventory (buffer_id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT, material_id TEXT, location TEXT, tier_boundary TEXT, min_level REAL, max_level REAL, reorder_qty REAL, current_qty REAL DEFAULT 0, uom TEXT, last_replenished TEXT, notes TEXT);
CREATE TABLE IF NOT EXISTS shipping_costs (plant_id TEXT NOT NULL, customer_id TEXT NOT NULL, cost_per_kft REAL NOT NULL, PRIMARY KEY (plant_id, customer_id));
CREATE TABLE IF NOT EXISTS packaging_specs (spec_id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id TEXT, product_id TEXT, reel_type_id TEXT, label_format TEXT, box_qty INTEGER DEFAULT 1, special_instructions TEXT);
CREATE TABLE IF NOT EXISTS environmental_readings (reading_id INTEGER PRIMARY KEY AUTOINCREMENT, wc_id TEXT NOT NULL, timestamp TEXT DEFAULT (datetime('now')), temperature_f REAL, humidity_pct REAL, shift TEXT, status TEXT DEFAULT 'OK');

-- Audit / Compliance
CREATE TABLE IF NOT EXISTS audit_trail (audit_id INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT NOT NULL, record_id TEXT, field_changed TEXT, old_value TEXT, new_value TEXT, changed_by INTEGER, changed_datetime TEXT DEFAULT (datetime('now')), change_reason TEXT, e_signature TEXT);
CREATE TABLE IF NOT EXISTS compliance_workflows (workflow_id INTEGER PRIMARY KEY AUTOINCREMENT, workflow_name TEXT NOT NULL, workflow_type TEXT, product_family TEXT, trigger_event TEXT, steps TEXT, required_docs TEXT, notes TEXT);

-- Simulation
CREATE TABLE IF NOT EXISTS simulation_events (sim_event_id INTEGER PRIMARY KEY AUTOINCREMENT, simulation_run_id TEXT, event_type TEXT NOT NULL, wc_id TEXT, job_id TEXT, event_time REAL, wall_time TEXT DEFAULT (datetime('now')), details TEXT);
CREATE TABLE IF NOT EXISTS simulation_state (wc_id TEXT PRIMARY KEY, status TEXT DEFAULT 'idle', current_job TEXT, queue_length INTEGER DEFAULT 0, utilization REAL DEFAULT 0, last_updated TEXT DEFAULT (datetime('now')));

-- Energy Metering
CREATE TABLE IF NOT EXISTS energy_readings (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    wc_id TEXT NOT NULL,
    kw_draw REAL NOT NULL,
    kwh_cumulative REAL DEFAULT 0,
    timestamp TEXT DEFAULT (datetime('now')),
    reading_type TEXT DEFAULT 'metered'
);
CREATE INDEX IF NOT EXISTS idx_energy_wc ON energy_readings(wc_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wo_status ON work_orders(status);
CREATE INDEX IF NOT EXISTS idx_wo_product ON work_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_wo_due ON work_orders(due_date);
CREATE INDEX IF NOT EXISTS idx_ops_wo ON operations(wo_id);
CREATE INDEX IF NOT EXISTS idx_ops_wc ON operations(wc_id);
CREATE INDEX IF NOT EXISTS idx_lot_output ON lot_tracking(output_lot);
CREATE INDEX IF NOT EXISTS idx_lot_input ON lot_tracking(input_lot);
CREATE INDEX IF NOT EXISTS idx_spc_wc ON spc_readings(wc_id);
CREATE INDEX IF NOT EXISTS idx_spc_param ON spc_readings(parameter_name);
CREATE INDEX IF NOT EXISTS idx_routing_product ON routings(product_id);
CREATE INDEX IF NOT EXISTS idx_pdl_wc ON process_data_live(wc_id);
CREATE INDEX IF NOT EXISTS idx_downtime_wc ON downtime_log(wc_id);
CREATE INDEX IF NOT EXISTS idx_scrap_wc ON scrap_log(wc_id);
CREATE INDEX IF NOT EXISTS idx_spark_reel ON spark_test_log(reel_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_reel_status ON reel_inventory(status);
CREATE INDEX IF NOT EXISTS idx_cert_person ON personnel_certs(person_id);
CREATE INDEX IF NOT EXISTS idx_maint_equip ON maintenance(equipment_id);
CREATE INDEX IF NOT EXISTS idx_env_wc ON environmental_readings(wc_id);

-- Wire Marking / Print Verification
CREATE TABLE IF NOT EXISTS print_marking (
    mark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    wo_id TEXT, reel_id TEXT, product_id TEXT,
    wc_id TEXT DEFAULT 'CUT-1',
    print_legend TEXT NOT NULL,
    print_method TEXT DEFAULT 'Inkjet',
    color TEXT DEFAULT 'White',
    character_height_mm REAL DEFAULT 2.5,
    footage_interval_ft REAL DEFAULT 1.0,
    voltage_rating TEXT, ul_listing TEXT,
    manufacturer_name TEXT DEFAULT 'SodhiCable LLC',
    verification_status TEXT DEFAULT 'Pending',
    verified_by INTEGER, verified_date TEXT,
    legibility_pass INTEGER, adhesion_pass INTEGER, spacing_pass INTEGER,
    notes TEXT, timestamp TEXT DEFAULT (datetime('now'))
);

-- Downtime reason codes (sub-categories)
CREATE TABLE IF NOT EXISTS reason_codes (
    code_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    reason_code TEXT NOT NULL UNIQUE,
    description TEXT,
    is_planned INTEGER DEFAULT 0
);

-- Scrap reason codes (sub-categories)
CREATE TABLE IF NOT EXISTS scrap_reason_codes (
    code_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cause_code TEXT NOT NULL,
    sub_code TEXT NOT NULL UNIQUE,
    description TEXT,
    corrective_action TEXT
);

-- ==================== LEVEL 4 ERP TABLES ====================

-- Purchase Orders: converts MRP planned orders into actual POs to suppliers
CREATE TABLE IF NOT EXISTS purchase_orders (
    po_id TEXT PRIMARY KEY,
    supplier TEXT NOT NULL,
    material_id TEXT NOT NULL REFERENCES materials(material_id),
    quantity REAL NOT NULL,
    unit_cost REAL NOT NULL,
    total_cost REAL,
    order_date TEXT DEFAULT (datetime('now')),
    expected_delivery TEXT,
    actual_delivery TEXT,
    status TEXT DEFAULT 'Draft',
    created_by TEXT DEFAULT 'ERP_SIM',
    approved_by TEXT,
    approved_date TEXT,
    notes TEXT
);

-- Goods Receipts: receiving inspection when PO materials arrive
CREATE TABLE IF NOT EXISTS goods_receipts (
    gr_id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id TEXT NOT NULL REFERENCES purchase_orders(po_id),
    material_id TEXT NOT NULL,
    qty_received REAL NOT NULL,
    qty_accepted REAL,
    qty_rejected REAL DEFAULT 0,
    receipt_date TEXT DEFAULT (datetime('now')),
    inspector TEXT,
    inspection_result TEXT DEFAULT 'Pending',
    lot_number TEXT,
    notes TEXT
);

-- Shipments: links WO completion to customer delivery
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    sales_order_id TEXT REFERENCES sales_orders(sales_order_id),
    wo_id TEXT,
    customer_id TEXT,
    ship_date TEXT DEFAULT (datetime('now')),
    carrier TEXT,
    tracking TEXT,
    qty_shipped REAL,
    status TEXT DEFAULT 'Pending',
    notes TEXT
);

-- Invoices: order-to-cash completion
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    sales_order_id TEXT REFERENCES sales_orders(sales_order_id),
    customer_id TEXT REFERENCES customers(customer_id),
    invoice_date TEXT DEFAULT (datetime('now')),
    due_date TEXT,
    subtotal REAL DEFAULT 0,
    tax REAL DEFAULT 0,
    total REAL DEFAULT 0,
    status TEXT DEFAULT 'Draft',
    payment_date TEXT,
    notes TEXT
);

-- Demand Forecast: statistical forecast at product-family level
CREATE TABLE IF NOT EXISTS demand_forecast (
    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_family TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_type TEXT DEFAULT 'week',
    forecast_qty REAL NOT NULL,
    actual_qty REAL,
    forecast_method TEXT DEFAULT 'SES',
    alpha REAL DEFAULT 0.3,
    created_date TEXT DEFAULT (datetime('now')),
    notes TEXT
);

-- S&OP Plan: aggregate planning decisions per period per family
CREATE TABLE IF NOT EXISTS sop_plan (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_version INTEGER DEFAULT 1,
    product_family TEXT NOT NULL,
    period_start TEXT NOT NULL,
    demand_forecast REAL DEFAULT 0,
    production_plan REAL DEFAULT 0,
    beginning_inventory REAL DEFAULT 0,
    ending_inventory REAL DEFAULT 0,
    capacity_required_hrs REAL DEFAULT 0,
    capacity_available_hrs REAL DEFAULT 0,
    capacity_gap REAL DEFAULT 0,
    status TEXT DEFAULT 'Draft',
    approved_by TEXT,
    approved_date TEXT,
    notes TEXT
);

-- Financial Ledger: simplified GL entries for cost tracking
CREATE TABLE IF NOT EXISTS financial_ledger (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT DEFAULT (datetime('now')),
    account_type TEXT NOT NULL,
    reference_type TEXT,
    reference_id TEXT,
    amount REAL NOT NULL,
    description TEXT,
    period TEXT
);

-- ISA-95 Message Log: L3-L4 boundary message tracking
CREATE TABLE IF NOT EXISTS isa95_messages (
    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    direction TEXT NOT NULL,
    message_type TEXT NOT NULL,
    source_system TEXT NOT NULL,
    target_system TEXT NOT NULL,
    payload_summary TEXT,
    reference_id TEXT,
    status TEXT DEFAULT 'Sent',
    processing_time_ms INTEGER
);

-- ERP Simulation State: tracks sim cycle and speed
CREATE TABLE IF NOT EXISTS erp_sim_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated TEXT DEFAULT (datetime('now'))
);

-- ERP Indexes
CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status);
CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier);
CREATE INDEX IF NOT EXISTS idx_gr_po ON goods_receipts(po_id);
CREATE INDEX IF NOT EXISTS idx_inv_so ON invoices(sales_order_id);
CREATE INDEX IF NOT EXISTS idx_ship_so ON shipments(sales_order_id);
CREATE INDEX IF NOT EXISTS idx_forecast_family ON demand_forecast(product_family);
CREATE INDEX IF NOT EXISTS idx_sop_family ON sop_plan(product_family);
CREATE INDEX IF NOT EXISTS idx_ledger_period ON financial_ledger(period);
CREATE INDEX IF NOT EXISTS idx_isa95_dir ON isa95_messages(direction);
CREATE INDEX IF NOT EXISTS idx_isa95_type ON isa95_messages(message_type);
