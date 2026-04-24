-- name: oee_by_wc
SELECT * FROM vw_oee

-- name: oee_trend
SELECT shift_date, wc_id, oee_overall, oee_availability, oee_performance, oee_quality FROM shift_reports ORDER BY shift_date ASC

-- name: scrap_pareto
SELECT * FROM vw_scrap_pareto

-- name: schedule_adherence
SELECT * FROM vw_schedule_adherence
