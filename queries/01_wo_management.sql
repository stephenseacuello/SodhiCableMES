-- name: wo_list_by_priority
SELECT wo.wo_id, wo.product_id, p.name AS product_name, p.family, wo.business_unit, wo.order_qty_kft, wo.priority, wo.due_date, wo.status, wo.created_date, CAST(julianday(wo.due_date)-julianday('now') AS INTEGER) AS days_remaining FROM work_orders wo JOIN products p ON p.product_id=wo.product_id ORDER BY wo.priority ASC, wo.due_date ASC

-- name: wo_bom_explosion
WITH RECURSIVE bom_tree AS (SELECT bm.product_id AS parent, bm.material_id, m.name AS material_name, bm.qty_per_kft, bm.scrap_factor, 1 AS level FROM bom_materials bm JOIN materials m ON m.material_id=bm.material_id WHERE bm.product_id=:product_id UNION ALL SELECT bt.parent, bm2.material_id, m2.name, bm2.qty_per_kft, bm2.scrap_factor, bt.level+1 FROM bom_tree bt JOIN bom_materials bm2 ON bm2.product_id=bt.material_id JOIN materials m2 ON m2.material_id=bm2.material_id WHERE bt.level<5) SELECT * FROM bom_tree

-- name: wo_completion_status
SELECT wo.wo_id, wo.product_id, wo.order_qty_kft, wo.status, wo.planned_start, wo.actual_start, wo.due_date FROM work_orders wo WHERE wo.status NOT IN ('Cancelled') ORDER BY wo.due_date ASC
