-- name: forward_trace
WITH RECURSIVE trace AS (SELECT output_lot, input_lot, wo_id, qty_consumed, uom, tier_level, 0 AS depth FROM lot_tracking WHERE input_lot=:lot_number UNION ALL SELECT lt.output_lot, lt.input_lot, lt.wo_id, lt.qty_consumed, lt.uom, lt.tier_level, t.depth+1 FROM lot_tracking lt JOIN trace t ON lt.input_lot=t.output_lot WHERE t.depth<10) SELECT DISTINCT output_lot, input_lot, wo_id, qty_consumed, uom, tier_level, depth FROM trace ORDER BY depth

-- name: backward_trace
WITH RECURSIVE trace AS (SELECT output_lot, input_lot, input_material_id, wo_id, qty_consumed, 0 AS depth FROM lot_tracking WHERE output_lot=:lot_number UNION ALL SELECT lt.output_lot, lt.input_lot, lt.input_material_id, lt.wo_id, lt.qty_consumed, t.depth+1 FROM lot_tracking lt JOIN trace t ON lt.output_lot=t.input_lot WHERE t.depth<10) SELECT * FROM trace ORDER BY depth

-- name: reel_inventory
SELECT reel_id, reel_type_id, wo_id, lot_id, product_id, footage_ft, status, created_date FROM reel_inventory ORDER BY created_date DESC
