-- name: personnel_list
SELECT person_id, employee_code, employee_name, department, job_title, role, shift, certification_level FROM personnel WHERE active=1 ORDER BY shift, employee_name

-- name: cert_expirations
SELECT * FROM vw_cert_expirations

-- name: shift_coverage
SELECT shift, COUNT(*) AS headcount FROM personnel WHERE active=1 GROUP BY shift
