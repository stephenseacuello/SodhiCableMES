-- name: material_availability
SELECT * FROM vw_material_availability

-- name: buffer_status
SELECT * FROM vw_buffer_status

-- name: inventory_by_location
SELECT i.inv_id, i.material_id, m.name, i.location_code, i.lot_number, i.qty_on_hand, i.qty_allocated, i.qty_on_hand-i.qty_allocated AS available, i.status FROM inventory i JOIN materials m ON m.material_id=i.material_id ORDER BY i.material_id
