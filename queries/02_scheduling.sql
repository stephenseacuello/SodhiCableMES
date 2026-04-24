-- name: pending_ops_by_wc
SELECT o.operation_id, o.wo_id, o.wc_id, o.operation_name, o.status, wo.priority, wo.due_date, wo.order_qty_kft, r.process_time_min_per_100ft FROM operations o JOIN work_orders wo ON wo.wo_id=o.wo_id LEFT JOIN routings r ON r.product_id=wo.product_id AND r.wc_id=o.wc_id WHERE o.status IN ('Pending','InProcess') ORDER BY o.wc_id, wo.priority ASC

-- name: wc_capacity_utilization
SELECT wc.wc_id, wc.name, wc.capacity_hrs_per_week, wc.utilization_target, COALESCE(SUM(o.run_time_min+o.setup_time_min)/60.0,0) AS current_load_hrs FROM work_centers wc LEFT JOIN operations o ON o.wc_id=wc.wc_id AND o.status IN ('Pending','InProcess') GROUP BY wc.wc_id ORDER BY wc.wc_id

-- name: gantt_chart_data
SELECT o.operation_id, o.wo_id, o.wc_id, o.operation_name, o.planned_start, o.planned_end, o.actual_start, o.actual_end, o.status FROM operations o WHERE o.status != 'Cancelled' ORDER BY o.planned_start
