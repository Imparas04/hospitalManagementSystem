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

-- [Phase 4] Emergency queue: waiting patients ordered most urgent first
SELECT t.id, p.patient_code, p.full_name, t.priority_level, t.priority_score, t.symptoms, t.recorded_at
FROM triage_records t
JOIN patients p ON p.id = t.patient_id
WHERE t.status = 'waiting'
ORDER BY t.priority_score DESC, t.recorded_at ASC;

-- [Phase 4] GROUP BY: how many emergency cases per priority level today
SELECT priority_level, COUNT(*) AS cases
FROM triage_records
WHERE DATE(recorded_at) = CURDATE()
GROUP BY priority_level
ORDER BY FIELD(priority_level, 'critical', 'high', 'medium', 'low');

-- [Phase 4] Multiple JOINs: which bed/ward each resolved emergency ended up in
SELECT p.full_name, t.priority_level, w.name AS ward, b.bed_number
FROM triage_records t
JOIN patients p ON p.id = t.patient_id
JOIN admissions ad ON ad.id = t.admission_id
JOIN beds b ON b.id = ad.bed_id
JOIN wards w ON w.id = b.ward_id;

-- [Phase 5] Pending lab work: tests ordered but result not yet entered, oldest first
SELECT lo.id, p.patient_code, p.full_name AS patient, lt.code AS test, lo.status, lo.ordered_at
FROM lab_orders lo
JOIN patients p ON p.id = lo.patient_id
JOIN lab_tests lt ON lt.id = lo.lab_test_id
WHERE lo.status IN ('ordered', 'sample_collected', 'processing')
ORDER BY lo.ordered_at;

-- [Phase 5] GROUP BY + HAVING: lab tests ordered more than once, with how many were abnormal
SELECT lt.code, COUNT(lo.id) AS times_ordered,
       SUM(CASE WHEN lr.is_abnormal THEN 1 ELSE 0 END) AS abnormal_results
FROM lab_tests lt
JOIN lab_orders lo ON lo.lab_test_id = lt.id
LEFT JOIN lab_results lr ON lr.lab_order_id = lo.id
GROUP BY lt.id, lt.code
HAVING COUNT(lo.id) > 1;

-- [Phase 5] Medicines expiring within the next 30 days (requirement-document example)
SELECT m.name, ms.batch_number, ms.expiry_date, ms.available_quantity,
       DATEDIFF(ms.expiry_date, CURDATE()) AS days_left
FROM medicine_stock ms
JOIN medicines m ON m.id = ms.medicine_id
WHERE ms.available_quantity > 0
  AND ms.expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
ORDER BY ms.expiry_date;

-- [Phase 5] Subquery: medicines whose total non-expired stock is below their reorder level (low-stock alert)
SELECT m.name, m.reorder_level,
       COALESCE((SELECT SUM(ms.available_quantity) FROM medicine_stock ms
                 WHERE ms.medicine_id = m.id AND ms.expiry_date >= CURDATE()), 0) AS total_available
FROM medicines m
WHERE COALESCE((SELECT SUM(ms.available_quantity) FROM medicine_stock ms
                WHERE ms.medicine_id = m.id AND ms.expiry_date >= CURDATE()), 0) < m.reorder_level;

-- [Phase 5] CTE + window function: most-prescribed medicines, ranked
WITH prescribed AS (
    SELECT m.name, SUM(pi.quantity_prescribed) AS total_prescribed
    FROM prescription_items pi
    JOIN medicines m ON m.id = pi.medicine_id
    GROUP BY m.id, m.name
)
SELECT name, total_prescribed, RANK() OVER (ORDER BY total_prescribed DESC) AS popularity_rank
FROM prescribed;

-- [Phase 6] Monthly hospital revenue (requirement-document example): money actually received per month
SELECT DATE_FORMAT(paid_at, '%Y-%m') AS month, COUNT(*) AS payments, SUM(amount) AS revenue
FROM payments
GROUP BY DATE_FORMAT(paid_at, '%Y-%m')
ORDER BY month;

-- [Phase 6] Revenue by payment method, with each method's share of the total (window function)
SELECT method, SUM(amount) AS received,
       ROUND(100 * SUM(amount) / SUM(SUM(amount)) OVER (), 1) AS percent_of_total
FROM payments
GROUP BY method
ORDER BY received DESC;

-- [Phase 6] Outstanding dues: patients who still owe money (INNER JOIN + GROUP BY + HAVING)
SELECT p.patient_code, p.full_name, COUNT(b.id) AS open_bills,
       SUM(b.total_amount - b.amount_paid) AS total_due
FROM bills b
JOIN patients p ON p.id = b.patient_id
WHERE b.status <> 'paid'
GROUP BY p.id, p.patient_code, p.full_name
HAVING SUM(b.total_amount - b.amount_paid) > 0
ORDER BY total_due DESC;

-- [Phase 6] Where the money comes from: revenue by charge category (CTE)
WITH category_totals AS (
    SELECT category, SUM(amount) AS billed
    FROM bill_items
    GROUP BY category
)
SELECT category, billed, ROUND(100 * billed / SUM(billed) OVER (), 1) AS percent_of_billing
FROM category_totals
ORDER BY billed DESC;

-- [Phase 6] Running total of payments per bill (window function)
SELECT b.bill_number, pay.receipt_number, pay.amount,
       SUM(pay.amount) OVER (PARTITION BY pay.bill_id ORDER BY pay.id) AS paid_so_far,
       b.total_amount - SUM(pay.amount) OVER (PARTITION BY pay.bill_id ORDER BY pay.id) AS balance_after
FROM payments pay
JOIN bills b ON b.id = pay.bill_id
ORDER BY pay.bill_id, pay.id;

-- [Phase 6] Length of stay per discharged admission with the doctor and diagnosis (multiple JOINs)
SELECT p.full_name AS patient, u.full_name AS doctor, w.name AS ward, ds.diagnosis,
       DATEDIFF(a.discharge_date, a.admission_date) + 1 AS days_stayed, ds.follow_up_date
FROM discharge_summaries ds
JOIN admissions a ON a.id = ds.admission_id
JOIN patients p ON p.id = a.patient_id
JOIN doctors d ON d.id = a.doctor_id
JOIN users u ON u.id = d.user_id
JOIN beds b ON b.id = a.bed_id
JOIN wards w ON w.id = b.ward_id;

-- ============================================================
-- Phase 7 queries. NOTE: the API converts "today"/"this month" to the hospital's timezone
-- (database timestamps are UTC). These plain-SQL versions use the database server's clock.
-- ============================================================

-- [Phase 7] Admin dashboard in ONE query: eight scalar subqueries
SELECT
  (SELECT COUNT(*) FROM patients WHERE is_active = TRUE)                                   AS total_patients,
  (SELECT COUNT(*) FROM appointments WHERE appointment_date = CURDATE() AND status <> 'cancelled') AS todays_appointments,
  (SELECT COUNT(*) FROM beds WHERE status = 'available')                                   AS available_beds,
  (SELECT COUNT(*) FROM beds WHERE status = 'occupied')                                    AS occupied_beds,
  (SELECT COUNT(*) FROM triage_records WHERE status IN ('waiting','bed_assigned','in_treatment')) AS emergency_patients,
  (SELECT COUNT(*) FROM lab_orders WHERE status IN ('ordered','sample_collected','processing'))   AS pending_lab_tests,
  (SELECT COUNT(*) FROM medicines m WHERE m.is_active = TRUE AND
        COALESCE((SELECT SUM(s.available_quantity) FROM medicine_stock s
                  WHERE s.medicine_id = m.id AND s.expiry_date >= CURDATE()), 0) < m.reorder_level) AS low_stock_medicines,
  (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE DATE(paid_at) = CURDATE())          AS todays_revenue;

-- [Phase 7] Patient registration trend with a running total (GROUP BY + window function)
SELECT DATE(created_at) AS day, COUNT(*) AS new_patients,
       SUM(COUNT(*)) OVER (ORDER BY DATE(created_at)) AS total_so_far
FROM patients
GROUP BY DATE(created_at)
ORDER BY day;

-- [Phase 7] Bed occupancy per ward (conditional aggregation)
SELECT w.name AS ward, COUNT(b.id) AS total_beds,
       SUM(b.status = 'occupied')    AS occupied,
       SUM(b.status = 'available')   AS available,
       SUM(b.status = 'maintenance') AS maintenance,
       ROUND(100 * SUM(b.status = 'occupied') / COUNT(b.id), 1) AS occupancy_percent
FROM wards w
LEFT JOIN beds b ON b.ward_id = w.id
GROUP BY w.id, w.name;

-- [Phase 7] Monthly billed vs collected (two CTEs + UNION, because MySQL has no FULL OUTER JOIN)
WITH billed AS (
    SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, SUM(total_amount) AS billed FROM bills GROUP BY 1
), collected AS (
    SELECT DATE_FORMAT(paid_at, '%Y-%m') AS month, SUM(amount) AS collected FROM payments GROUP BY 1
), months AS (
    SELECT month FROM billed UNION SELECT month FROM collected
)
SELECT m.month, COALESCE(b.billed, 0) AS billed, COALESCE(c.collected, 0) AS collected
FROM months m
LEFT JOIN billed b ON b.month = m.month
LEFT JOIN collected c ON c.month = m.month
ORDER BY m.month;

-- [Phase 7] AUDIT: who did the most in the last 7 days, ranked (GROUP BY + RANK window function)
SELECT username, role, COUNT(*) AS actions,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS activity_rank
FROM audit_logs
WHERE user_id IS NOT NULL AND created_at >= NOW() - INTERVAL 7 DAY
GROUP BY user_id, username, role;

-- [Phase 7] AUDIT: complete history of one patient record (INNER JOIN)
SELECT al.created_at, al.username, al.role, al.action, al.description
FROM audit_logs al
JOIN patients p ON p.id = al.entity_id AND al.entity_type = 'Patient'
WHERE p.patient_code = 'P2026000001'
ORDER BY al.created_at;

-- [Phase 7] AUDIT / SECURITY: usernames with 3 or more failed logins (HAVING)
SELECT username, COUNT(*) AS failed_attempts, MAX(created_at) AS last_attempt
FROM audit_logs
WHERE action = 'auth.login_failed'
GROUP BY username
HAVING COUNT(*) >= 3
ORDER BY failed_attempts DESC;

-- [Phase 7] NOTIFICATIONS: unread count per user (CTE + LEFT JOIN anti-join)
WITH visible AS (
    SELECT u.id AS user_id, n.id AS notification_id
    FROM users u
    JOIN roles r ON r.id = u.role_id
    JOIN notifications n ON n.resolved_at IS NULL
         AND (n.target_user_id = u.id OR (n.target_user_id IS NULL AND n.target_role = r.name))
)
SELECT u.username, COUNT(v.notification_id) AS unread
FROM users u
LEFT JOIN visible v ON v.user_id = u.id
LEFT JOIN notification_reads nr ON nr.notification_id = v.notification_id AND nr.user_id = u.id
WHERE nr.id IS NULL
GROUP BY u.id, u.username;
