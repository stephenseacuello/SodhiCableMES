-- SodhiCable MES v4.0 — 8 Analytical Views

CREATE VIEW IF NOT EXISTS vw_oee AS
SELECT wc.wc_id, wc.name AS wc_name,
  ROUND(AVG(sr.oee_availability)*100,1) AS availability_pct,
  ROUND(AVG(sr.oee_performance)*100,1) AS performance_pct,
  ROUND(AVG(sr.oee_quality)*100,1) AS quality_pct,
  ROUND(AVG(sr.oee_overall)*100,1) AS oee_pct
FROM work_centers wc LEFT JOIN shift_reports sr ON sr.wc_id=wc.wc_id
GROUP BY wc.wc_id, wc.name;

CREATE VIEW IF NOT EXISTS vw_material_availability AS
SELECT m.material_id, m.name AS material_name, m.unit_cost, m.lead_time_days,
  m.safety_stock_qty, COALESCE(inv.total_on_hand,0) AS total_on_hand,
  COALESCE(inv.total_allocated,0) AS total_allocated,
  COALESCE(inv.total_on_hand,0)-COALESCE(inv.total_allocated,0) AS qty_available,
  COALESCE(d.total_demand,0) AS total_demand,
  (COALESCE(inv.total_on_hand,0)-COALESCE(inv.total_allocated,0))-COALESCE(d.total_demand,0) AS surplus_deficit
FROM materials m
LEFT JOIN (SELECT material_id, SUM(qty_on_hand) AS total_on_hand, SUM(qty_allocated) AS total_allocated FROM inventory GROUP BY material_id) inv ON inv.material_id=m.material_id
LEFT JOIN (SELECT bm.material_id, SUM(bm.qty_per_kft*wo.order_qty_kft) AS total_demand FROM bom_materials bm JOIN work_orders wo ON wo.product_id=bm.product_id WHERE wo.status IN ('Pending','Released','InProcess') GROUP BY bm.material_id) d ON d.material_id=m.material_id
ORDER BY surplus_deficit ASC;

CREATE VIEW IF NOT EXISTS vw_wo_status_summary AS
SELECT wo.wo_id, wo.product_id, p.name AS product_name, p.family,
  wo.business_unit, wo.order_qty_kft, wo.priority, wo.due_date, wo.status,
  CAST(julianday(wo.due_date)-julianday('now') AS INTEGER) AS days_until_due,
  CASE WHEN wo.status NOT IN ('Complete','Cancelled') AND wo.due_date IS NOT NULL AND julianday(wo.due_date)<julianday('now') THEN 1 ELSE 0 END AS is_overdue
FROM work_orders wo JOIN products p ON p.product_id=wo.product_id
ORDER BY wo.priority ASC, wo.due_date ASC;

CREATE VIEW IF NOT EXISTS vw_buffer_status AS
SELECT bi.buffer_id, COALESCE(p.name,m.name) AS item_name, bi.tier_boundary,
  bi.current_qty, bi.min_level, bi.max_level, bi.uom,
  CASE WHEN bi.current_qty<=bi.min_level THEN 'REORDER' WHEN bi.current_qty<=bi.min_level*1.2 THEN 'LOW' ELSE 'OK' END AS buffer_status
FROM buffer_inventory bi LEFT JOIN products p ON p.product_id=bi.product_id LEFT JOIN materials m ON m.material_id=bi.material_id;

CREATE VIEW IF NOT EXISTS vw_schedule_adherence AS
SELECT wo.wo_id, wo.product_id, p.name AS product_name, wo.due_date, wo.status,
  CASE WHEN wo.status='Complete' AND wo.actual_end<=wo.due_date THEN 'On Time'
       WHEN wo.status='Complete' AND wo.actual_end>wo.due_date THEN 'Late'
       WHEN wo.status NOT IN ('Complete','Cancelled') AND julianday(wo.due_date)<julianday('now') THEN 'Overdue'
       ELSE 'In Progress' END AS adherence_status
FROM work_orders wo JOIN products p ON p.product_id=wo.product_id WHERE wo.status!='Cancelled';

CREATE VIEW IF NOT EXISTS vw_scrap_pareto AS
SELECT sl.cause_code, SUM(sl.quantity_ft) AS total_scrap_ft, COUNT(*) AS event_count,
  ROUND(SUM(sl.quantity_ft)*100.0/(SELECT SUM(quantity_ft) FROM scrap_log),1) AS scrap_pct
FROM scrap_log sl GROUP BY sl.cause_code ORDER BY total_scrap_ft DESC;

CREATE VIEW IF NOT EXISTS vw_cert_expirations AS
SELECT p.person_id, p.employee_name, p.role, pc.wc_id, pc.certification_type,
  pc.cert_level, pc.expiry_date,
  CAST(julianday(pc.expiry_date)-julianday('now') AS INTEGER) AS days_until_expiry,
  CASE WHEN julianday(pc.expiry_date)<julianday('now') THEN 'EXPIRED'
       WHEN julianday(pc.expiry_date)-julianday('now')<30 THEN 'EXPIRING SOON'
       ELSE 'VALID' END AS cert_status
FROM personnel p JOIN personnel_certs pc ON pc.person_id=p.person_id WHERE p.active=1
ORDER BY pc.expiry_date ASC;

CREATE VIEW IF NOT EXISTS vw_maintenance_due AS
SELECT e.equipment_id, e.equipment_code, e.description, e.work_center_id AS wc_id,
  ms.pm_type, ms.next_due,
  CAST(julianday(ms.next_due)-julianday('now') AS INTEGER) AS days_until_due,
  CASE WHEN julianday(ms.next_due)<julianday('now') THEN 'OVERDUE'
       WHEN julianday(ms.next_due)-julianday('now')<7 THEN 'DUE SOON'
       ELSE 'OK' END AS pm_status
FROM equipment e JOIN maintenance_schedule ms ON ms.equipment_id=e.equipment_id
ORDER BY ms.next_due ASC;

-- Supplier Performance Scorecard (#12)
CREATE VIEW IF NOT EXISTS vw_supplier_scorecard AS
SELECT m.supplier,
  COUNT(DISTINCT m.material_id) AS materials_supplied,
  ROUND(AVG(m.lead_time_days), 1) AS avg_lead_time,
  COALESCE(SUM(i.qty_on_hand), 0) AS total_on_hand,
  ROUND(AVG(CASE WHEN i.status = 'Available' THEN 1.0 ELSE 0.0 END) * 100, 1) AS availability_pct
FROM materials m
LEFT JOIN inventory i ON i.material_id = m.material_id
WHERE m.supplier IS NOT NULL
GROUP BY m.supplier
ORDER BY m.supplier;
