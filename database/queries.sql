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
