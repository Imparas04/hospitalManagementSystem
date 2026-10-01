-- Advanced SQL examples. This file grows phase by phase; the full set is completed in Phase 8.
USE hospital_db;

-- [Phase 1] INNER JOIN + GROUP BY: how many users does each role have?
SELECT r.name AS role, COUNT(u.id) AS total_users
FROM roles r
LEFT JOIN users u ON u.role_id = r.id      -- LEFT JOIN keeps roles that have 0 users
GROUP BY r.id, r.name
ORDER BY total_users DESC;

-- [Phase 1] INNER JOIN: list active staff with their role name
SELECT u.id, u.username, u.full_name, r.name AS role
FROM users u
INNER JOIN roles r ON r.id = u.role_id
WHERE u.is_active = TRUE;

-- [Phase 2] Multiple JOINs: patient + who registered them + how many visits they have
SELECT p.patient_code, p.full_name, u.full_name AS registered_by,
       COUNT(v.id) AS total_visits
FROM patients p
INNER JOIN users u ON u.id = p.created_by_id
LEFT JOIN visit_history v ON v.patient_id = p.id
GROUP BY p.id, p.patient_code, p.full_name, u.full_name
ORDER BY total_visits DESC;

-- [Phase 2] HAVING: patients registered as emergency with 2+ visits since
SELECT p.patient_code, p.full_name, COUNT(v.id) AS visit_count
FROM patients p
JOIN visit_history v ON v.patient_id = p.id
WHERE p.is_emergency_registration = TRUE
GROUP BY p.id, p.patient_code, p.full_name
HAVING COUNT(v.id) >= 2;

-- [Phase 2] Subquery: patients who have never had a visit recorded
SELECT patient_code, full_name
FROM patients p
WHERE NOT EXISTS (SELECT 1 FROM visit_history v WHERE v.patient_id = p.id);
