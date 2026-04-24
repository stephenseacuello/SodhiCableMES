-- name: recipe_list
SELECT r.recipe_id, r.recipe_code, r.description, r.product_id, r.work_center_id, r.version, r.status, r.effective_date FROM recipes r ORDER BY r.product_id, r.version DESC

-- name: recipe_parameters
SELECT rp.param_id, rp.recipe_id, rp.parameter_name, rp.parameter_value, rp.uom, rp.lower_limit, rp.upper_limit, rp.control_type FROM recipe_parameters rp WHERE rp.recipe_id=:recipe_id

-- name: document_list
SELECT doc_id, doc_type, doc_name, version, status, created_date FROM documents ORDER BY created_date DESC
