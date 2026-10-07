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

-- [Phase 3] INNER JOIN + GROUP BY + ORDER BY: appointment load per doctor
SELECT d.id AS doctor_id, u.full_name AS doctor_name, dept.name AS department,
       COUNT(a.id) AS total_appointments
FROM doctors d
INNER JOIN users u ON u.id = d.user_id
INNER JOIN departments dept ON dept.id = d.department_id
LEFT JOIN appointments a ON a.doctor_id = d.id AND a.status != 'cancelled'
GROUP BY d.id, u.full_name, dept.name
ORDER BY total_appointments DESC;

-- [Phase 3] Multiple JOINs: today's appointment list with patient + doctor + department
SELECT a.appointment_time, p.patient_code, p.full_name AS patient, u.full_name AS doctor,
       dept.name AS department, a.status
FROM appointments a
JOIN patients p ON p.id = a.patient_id
JOIN doctors d ON d.id = a.doctor_id
JOIN users u ON u.id = d.user_id
JOIN departments dept ON dept.id = a.department_id
WHERE a.appointment_date = CURDATE()
ORDER BY a.appointment_time;

-- [Phase 3] HAVING: departments with more than 1 appointment booked
SELECT dept.name, COUNT(a.id) AS appointment_count
FROM departments dept
JOIN appointments a ON a.department_id = dept.id
GROUP BY dept.id, dept.name
HAVING COUNT(a.id) > 1;

-- [Phase 3] Subquery: currently occupied beds, with which patient and ward
SELECT w.name AS ward, b.bed_number, p.full_name AS patient
FROM beds b
JOIN wards w ON w.id = b.ward_id
JOIN admissions ad ON ad.bed_id = b.id AND ad.status = 'admitted'
JOIN patients p ON p.id = ad.patient_id
WHERE b.id IN (SELECT bed_id FROM admissions WHERE status = 'admitted');

-- [Phase 3] Window function: rank doctors by appointment count within their department
SELECT dept.name AS department, u.full_name AS doctor, COUNT(a.id) AS appointments,
       RANK() OVER (PARTITION BY dept.id ORDER BY COUNT(a.id) DESC) AS rank_in_department
FROM doctors d
JOIN users u ON u.id = d.user_id
JOIN departments dept ON dept.id = d.department_id
LEFT JOIN appointments a ON a.doctor_id = d.id
GROUP BY dept.id, dept.name, d.id, u.full_name;
