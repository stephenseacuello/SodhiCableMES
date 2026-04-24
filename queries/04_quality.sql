-- name: spc_chart_data
SELECT spc_id, wo_id, wc_id, measurement_date, parameter_name, measured_value, subgroup_id, usl, lsl, ucl, cl, lcl, rule_violation, status FROM spc_readings WHERE wc_id=:wc_id AND parameter_name=:parameter ORDER BY measurement_date ASC

-- name: spc_all
SELECT spc_id, wc_id, measurement_date, parameter_name, measured_value, subgroup_id, ucl, cl, lcl, rule_violation, status FROM spc_readings ORDER BY measurement_date DESC LIMIT 200

-- name: ncr_list
SELECT ncr_id, product_id, wo_id, lot_number, defect_type, severity, reported_date, status, root_cause, corrective_action FROM ncr ORDER BY reported_date DESC

-- name: spark_test_trend
SELECT result, COUNT(*) AS cnt, ROUND(COUNT(CASE WHEN result='PASS' THEN 1 END)*100.0/COUNT(*),1) AS pass_rate FROM spark_test_log GROUP BY result
