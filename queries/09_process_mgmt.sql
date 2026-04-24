-- name: deviations
SELECT deviation_id, wo_id, wc_id, parameter_name, detection_method, deviation_value, setpoint_value, severity, timestamp, resolved FROM process_deviations ORDER BY timestamp DESC

-- name: holds
SELECT hold_id, wo_id, lot_number, hold_reason, held_date, hold_status, disposition FROM hold_release ORDER BY held_date DESC
