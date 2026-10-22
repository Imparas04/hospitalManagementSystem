# API Documentation - Phase 1 (Auth, Users, RBAC)

**Base URL (local):** `http://localhost:5000/api`

## Rules that apply to every endpoint

| Item | Value |
|---|---|
| Request body format | JSON. Header: `Content-Type: application/json` |
| Auth header (protected APIs) | `Authorization: Bearer <access_token>` |
| Success shape | `{"success": true, "message": "...", "data": {...}}` |
| Error shape | `{"success": false, "message": "...", "errors": {...}}` |

**Status codes used:** `200` OK, `201` Created, `400` validation error, `401` not logged in / bad or expired token, `403` logged in but wrong role, `404` not found, `409` duplicate, `500` server error, `503` DB unreachable.

**Important for frontend:** a `401` means "send the user to the login page". A `403` means "show 'not allowed'" (do not log out).

**Roles (exact strings):** `admin`, `receptionist`, `doctor`, `nurse`, `lab_technician`, `pharmacist`, `billing_staff`

**Password rule:** min 8 chars, at least 1 letter and 1 digit.

---

## 1. Health check
`GET /api/health` - Auth: **none**

Response `200`:
```json
{"success": true, "message": "API is running", "data": {"status": "ok"}}
```
Error `503`: database not reachable.

---

## 2. Login
`POST /api/auth/login` - Auth: **none**

Body:
```json
{"username": "admin", "password": "Admin12345"}
```
`username` accepts the username **or** the email.

Response `200`:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOi...",
    "token_type": "Bearer",
    "expires_in_seconds": 28800,
    "user": {"id": 1, "username": "admin", "email": "admin@hospital.local",
             "full_name": "System Administrator", "phone": null, "role": "admin",
             "is_active": true, "last_login_at": "2026-09-28T10:12:36", "created_at": "2026-09-28T10:12:29"}
  }
}
```
Errors: `400` (missing fields, `errors` has field names), `401` (`"Invalid username or password"` - same message for wrong user, wrong password and deactivated account).

**Frontend tip:** store `access_token` (e.g. in `localStorage`) and use `user.role` to pick the dashboard.

---

## 3. Current user
`GET /api/auth/me` - Auth: **any logged-in user**

Response `200`: `data` = the user object (same as above).
Errors: `401`.

---

## 4. Change own password
`POST /api/auth/change-password` - Auth: **any logged-in user**

Body:
```json
{"old_password": "Admin12345", "new_password": "NewPass12345"}
```
Response `200`: `{"success": true, "message": "Password changed successfully", "data": null}`
Errors: `400` (`errors` may contain `old_password` and/or `new_password`), `401`.

---

## 5. List roles
`GET /api/roles` - Auth: **admin only**

Response `200`: `data` = `[{"id": 1, "name": "admin", "description": "Full system access"}, ...]`
Errors: `401`, `403`.

---

## 6. Create user
`POST /api/users` - Auth: **admin only**

Body:
```json
{
  "username": "nurse.anita",
  "email": "anita@hospital.local",
  "password": "Nurse12345",
  "full_name": "Anita Sharma",
  "role": "nurse",
  "phone": "+919876543210"
}
```
`phone` is optional; everything else is required.

Response `201`: `data` = the created user (no password fields).
Errors: `400` (validation, e.g. `{"errors": {"role": "Role must be one of: ..."}}`), `401`, `403`, `409` (`errors` has `username` and/or `email`).

---

## 7. List users
`GET /api/users` - Auth: **admin only**

Query params (all optional):

| Param | Meaning |
|---|---|
| `role` | filter by role name, e.g. `?role=doctor` |
| `is_active` | `true` or `false` |
| `q` | search in full name / username / email |
| `page` | default `1` |
| `per_page` | default `10`, max `100` |

Response `200`:
```json
{"success": true, "message": "Users fetched",
 "data": {"items": [ {user}, {user} ], "page": 1, "per_page": 10, "total": 7, "pages": 1}}
```
Errors: `400` (bad page numbers), `401`, `403`.

---

## 8. Get one user
`GET /api/users/<id>` - Auth: **admin only** - Response `200` (user) - Errors: `401`, `403`, `404`.

## 9. Update user
`PUT /api/users/<id>` - Auth: **admin only**

Send only the fields you want to change: `username`, `email`, `full_name`, `phone`, `role`, `is_active` (boolean).
```json
{"full_name": "Anita S. Sharma", "role": "receptionist"}
```
Response `200`: updated user.
Errors: `400` (empty body / invalid values / admin trying to deactivate or change role of **own** account), `401`, `403`, `404`, `409` (duplicate username/email).

## 10. Deactivate user (soft delete)
`DELETE /api/users/<id>` - Auth: **admin only**

The user is **not** removed from the database (later phases reference users); `is_active` becomes `false`, so they can no longer log in and their existing token stops working immediately.
Errors: `400` (own account), `401`, `403`, `404`.
To re-activate: `PUT /api/users/<id>` with `{"is_active": true}`.

## 11. Reset a user's password
`POST /api/users/<id>/reset-password` - Auth: **admin only**

Body: `{"new_password": "Fresh12345"}` - Response `200`. Errors: `400`, `401`, `403`, `404`.

---

## Permission summary (Phase 1)

| Endpoint | Public | Any logged-in | Admin only |
|---|:-:|:-:|:-:|
| GET /api/health | X | | |
| POST /api/auth/login | X | | |
| GET /api/auth/me | | X | |
| POST /api/auth/change-password | | X | |
| GET /api/roles | | | X |
| POST/GET/PUT/DELETE /api/users..., reset-password | | | X |

The full role -> permission table for the whole project is already defined in `app/utils/permissions.py`; later phases attach these permissions to their routes with `@permission_required("patients:create")`.

## Sample calls (curl)
```bash
# login
curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"Admin12345"}'

# call a protected API
curl http://localhost:5000/api/users -H "Authorization: Bearer <access_token>"
```
Postman: import `postman/Hospital_Phase01.postman_collection.json` (the Login request saves the token automatically).

## JavaScript (fetch) example for the frontend
```js
const res = await fetch("http://localhost:5000/api/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password })
});
const json = await res.json();
if (json.success) localStorage.setItem("token", json.data.access_token);

// later
const users = await fetch("http://localhost:5000/api/users", {
  headers: { Authorization: "Bearer " + localStorage.getItem("token") }
}).then(r => r.json());
```
