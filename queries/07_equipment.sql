-- name: equipment_status
SELECT e.equipment_id, e.equipment_code, e.description, e.work_center_id, e.equipment_type, e.manufacturer, e.status, e.last_pm_date, e.next_pm_date, e.calibration_due, CAST(julianday(e.calibration_due)-julianday('now') AS INTEGER) AS cal_days_remaining FROM equipment e ORDER BY e.work_center_id

-- name: maintenance_due
SELECT * FROM vw_maintenance_due

-- name: downtime_pareto
SELECT wc_id, category, SUM(duration_min) AS total_min, COUNT(*) AS events FROM downtime_log GROUP BY wc_id, category ORDER BY total_min DESC
