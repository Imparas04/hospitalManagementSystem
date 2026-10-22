# API Documentation

This is a starting reference for routes confirmed in the project source review. Consult `backend/app/routes/` for the complete and current API surface. Protected endpoints may require authentication and role-based permissions.

## Base URL
Local development: `http://127.0.0.1:5000/api`

## Confirmed endpoints

| Method | Path | Purpose / access note |
|---|---|---|
| GET | `/patients` | List/search patients; requires `patients:read` |
| GET | `/doctors` | List/search doctors; requires `doctors:read` |
| GET | `/doctors/{doctor_id}` | Fetch a doctor; protected route |
| GET | `/pharmacy/medicines` | List/search medicines; requires `pharmacy:read` |
| GET | `/pharmacy/medicines/{medicine_id}` | Fetch a medicine; requires `pharmacy:read` |
| GET | `/analytics/department-patients` | Department/patient analytics |
| GET | `/analytics/emergency-cases` | Emergency analytics; requires `analytics:emergency` |

Other route modules include admissions, appointments, audit, auth, billing, discharge, lab, notifications, reports, triage, and users. Check each module under `backend/app/routes/` for exact methods, request schemas, and response formats.

## Authentication notes
A `401 Unauthorized` response commonly means credentials are missing or invalid. A `403 Forbidden` commonly means the authenticated user lacks a required permission. Follow the app's supported login/token flow; do not remove permission decorators to make requests work.

## 404 notes
A `404 Not Found` usually indicates a URL/method mismatch or a missing resource. The project has triage and emergency analytics routes, but the reviewed code did not confirm a top-level `GET /api/emergency` route. Verify exact paths in `triage.py` and `dashboard.py`.

The `backend/postman/` or `postman/` directory may contain collections for local API testing. Use test records and never publish tokens or sensitive patient data.
