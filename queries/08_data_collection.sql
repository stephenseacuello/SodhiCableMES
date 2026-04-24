-- name: recent_readings
SELECT reading_id, wc_id, parameter, value, timestamp, quality_flag FROM process_data_live ORDER BY timestamp DESC LIMIT 100

-- name: readings_by_wc
SELECT reading_id, parameter, value, timestamp, quality_flag FROM process_data_live WHERE wc_id=:wc_id ORDER BY timestamp DESC LIMIT 50
