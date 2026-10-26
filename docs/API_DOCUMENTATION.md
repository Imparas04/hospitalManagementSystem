# API Documentation

Base URL: `http://127.0.0.1:5000` · every endpoint below starts with `/api` (already included in the paths).
This table is generated from the route files in `backend/app/routes/`, so it matches the code.

## Response format

```json
{ "success": true,  "message": "Patient registered", "data": { "...": "..." } }
{ "success": false, "message": "Validation failed",   "errors": { "phone": "Phone is required" } }
```

* Send the token on every protected call: `Authorization: Bearer <access_token>`.
* `401` = no / expired / logged-out token · `403` = your role may not do this · `404` = not found ·
  `400` = validation problem (see `errors`) · `409` = business rule (e.g. no suitable bed) · `429` = too many failed logins.
* Lists that can be long are paged: `?page=1&per_page=20` → `data = {items, page, per_page, total, pages}` (max 100 per page).
* Dates are `YYYY-MM-DD`, times `HH:MM`, timestamps are UTC.

## Sign in

`POST /api/auth/login` with `{"username": "...", "password": "..."}` (username or email) returns `data.access_token` and `data.user`.
After 5 wrong passwords for the same username and address the answer is `429` with a `Retry-After` header.
`POST /api/auth/logout` makes the token unusable immediately.

## Endpoints

### Health

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/health` | public | Public endpoint: is the API up and is the database reachable? |

### Authentication

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/auth/login` | public | login |
| GET | `/api/auth/me` | any signed-in user | me |
| POST | `/api/auth/change-password` | any signed-in user | change password |
| POST | `/api/auth/logout` | any signed-in user | Make the current token useless right now (it can no longer be used even before it expires) |

### Users & roles (admin)

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/roles` | admin | list roles |
| POST | `/api/users` | admin | create user |
| GET | `/api/users` | admin | Query params: role, is_active (true/false), q (search name/username/email), page, per_page |
| GET | `/api/users/{user_id}` | admin | get user |
| PUT | `/api/users/{user_id}` | admin | update user |
| DELETE | `/api/users/{user_id}` | admin | Soft delete: we never remove users because later tables (audit logs, bills...) refer to them |
| POST | `/api/users/{user_id}/reset-password` | admin | reset password |

### Patients

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/patients` | permission `patients:create` | create patient |
| GET | `/api/patients` | permission `patients:read` | Query params: q (name/code/phone), gender, blood_group, emergency=true, |
| GET | `/api/patients/{patient_id}` | permission `patients:read` | get patient |
| PUT | `/api/patients/{patient_id}` | permission `patients:update` | update patient |
| DELETE | `/api/patients/{patient_id}` | permission `patients:update` | Soft delete - patient records are never hard-deleted (medical/legal history) |
| POST | `/api/patients/{patient_id}/medical-history` | permission `patients:update` | add medical history |
| GET | `/api/patients/{patient_id}/medical-history` | permission `patients:read` | list medical history |
| POST | `/api/patients/{patient_id}/visits` | permission `patients:update` | add visit |
| GET | `/api/patients/{patient_id}/visits` | permission `patients:read` | list visits |

### Departments, doctors & schedules

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/departments` | admin | create department |
| GET | `/api/departments` | permission `departments:read` | list departments |
| PUT | `/api/departments/{dept_id}` | admin | update department |
| POST | `/api/doctors` | admin | Links an existing user (role must be 'doctor') to a department + specialization |
| GET | `/api/doctors` | permission `doctors:read` | Query params: department_id, specialization, emergency_duty=true, q (name), is_active |
| GET | `/api/doctors/{doctor_id}` | permission `doctors:read` | get doctor |
| PUT | `/api/doctors/{doctor_id}` | admin | update doctor |
| POST | `/api/doctors/{doctor_id}/schedule` | admin | Add one weekly availability block, e.g. Mon 09:00-13:00 in 15-min slots |
| GET | `/api/doctors/{doctor_id}/schedule` | permission `doctors:read` | list schedule |
| GET | `/api/doctors/{doctor_id}/availability` | permission `appointments:read` | ?date=YYYY-MM-DD -> list of free 'HH:MM' slots for that day |

### Appointments

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/appointments` | permission `appointments:create` | Books the requested slot if free. If taken, the appointment is created as |
| GET | `/api/appointments` | permission `appointments:read` | Query params: doctor_id, patient_id, department_id, status, date (YYYY-MM-DD), page, per_page |
| GET | `/api/appointments/waiting-list` | permission `appointments:read` | Query params: doctor_id, department_id (optional filters) |
| GET | `/api/appointments/{appointment_id}` | permission `appointments:read` | get appointment |
| PUT | `/api/appointments/{appointment_id}` | permission `appointments:update` | Reschedule: send any of appointment_date, appointment_time, doctor_id, reason, notes |
| POST | `/api/appointments/{appointment_id}/cancel` | permission `appointments:update` | cancel appointment |
| POST | `/api/appointments/{appointment_id}/complete` | permission `appointments:update` | complete appointment |
| POST | `/api/appointments/{appointment_id}/no-show` | permission `appointments:update` | no show appointment |
| POST | `/api/appointments/{appointment_id}/promote` | permission `appointments:update` | Try to move a waitlisted appointment into its requested slot (e.g. after a cancellation freed it up) |

### Wards, beds & admissions

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/wards` | admin | create ward |
| GET | `/api/wards` | permission `wards:read` | list wards |
| POST | `/api/wards/{ward_id}/beds` | admin | add bed |
| GET | `/api/beds` | permission `beds:read` | Query params: ward_id, status (available/occupied/maintenance), bed_type |
| PUT | `/api/beds/{bed_id}` | permission `beds:update` | update bed |
| POST | `/api/admissions` | permission `admissions:create` | admit patient |
| GET | `/api/admissions` | permission `admissions:read` | Query params: patient_id, status (admitted/discharged), ward_id, page, per_page |
| GET | `/api/admissions/{admission_id}` | permission `admissions:read` | get admission |
| POST | `/api/admissions/{admission_id}/discharge` | permission `admissions:update` | discharge patient |

### Emergency triage

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/triage` | permission `triage:create` | Record vital signs for a patient. Priority level/score are calculated |
| GET | `/api/triage/queue` | permission `triage:read` | The emergency queue: waiting patients sorted most-urgent-first |
| GET | `/api/triage` | permission `triage:read` | Query params: status, priority_level, patient_id |
| GET | `/api/triage/{triage_id}` | permission `triage:read` | get triage |
| PUT | `/api/triage/{triage_id}/status` | permission `triage:update` | Move a patient through the emergency workflow: waiting -> bed_assigned |
| POST | `/api/triage/{triage_id}/allocate-bed` | permission `triage:update` | Automatic smart bed allocation for this triage record |
| POST | `/api/triage/{triage_id}/resolve` | permission `triage:update` | resolve triage |

### Laboratory

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/lab/tests` | admin, lab_technician | create test type |
| GET | `/api/lab/tests` | permission `lab:read` | list test types |
| POST | `/api/lab/orders` | permission `lab:order` | create order |
| GET | `/api/lab/orders` | permission `lab:read` | Query params: patient_id, doctor_id, status |
| GET | `/api/lab/orders/{order_id}` | permission `lab:read` | get order |
| PUT | `/api/lab/orders/{order_id}/status` | permission `lab:update` | Lab tech moves the order through: sample_collected -> processing |
| POST | `/api/lab/orders/{order_id}/result` | permission `lab:enter_result` | enter result |
| POST | `/api/lab/orders/{order_id}/review` | permission `lab:review` | Doctor reviews the entered result |

### Pharmacy & prescriptions

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/pharmacy/medicines` | admin, pharmacist | create medicine |
| GET | `/api/pharmacy/medicines` | permission `medicines:read` | Query params: q (search name), low_stock=true |
| GET | `/api/pharmacy/medicines/{medicine_id}` | permission `medicines:read` | get medicine |
| POST | `/api/pharmacy/medicines/{medicine_id}/batches` | permission `pharmacy:update` | add batch |
| POST | `/api/prescriptions` | permission `prescriptions:create` | create prescription |
| GET | `/api/prescriptions` | permission `prescriptions:read` | Query params: patient_id, doctor_id, status |
| GET | `/api/prescriptions/{prescription_id}` | permission `prescriptions:read` | get prescription |
| POST | `/api/prescriptions/{prescription_id}/issue` | permission `pharmacy:issue` | Issues as much of the prescription as stock allows (FEFO, skips expired |

### Billing & payments

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/bills/preview` | permission `billing:read` | Shows what WOULD be billed right now (nothing is saved). Query: patient_id or patient_code |
| POST | `/api/bills` | permission `billing:create` | Automatic billing: collects every unbilled service for the patient into one bill |
| GET | `/api/bills` | permission `billing:read` | Query: patient_id, patient_code, status (unpaid/partially_paid/paid), page, per_page |
| GET | `/api/bills/outstanding` | permission `billing:read` | Every bill that still has money due, oldest first, plus the grand total due |
| GET | `/api/bills/{bill_id}` | permission `billing:read` | get bill |
| POST | `/api/bills/{bill_id}/items` | permission `billing:update` | Add an 'other service' line (e.g. ambulance, dressing). Not allowed on a fully paid bill |
| PUT | `/api/bills/{bill_id}/adjust` | permission `billing:update` | Change discount % and/or tax %. Only before any payment has been taken |
| GET | `/api/bills/{bill_id}/pdf` | permission `billing:read` | bill pdf |
| POST | `/api/bills/{bill_id}/payments` | permission `payments:create` | Take a payment (partial or full, any method). Returns the receipt data |
| GET | `/api/payments/{payment_id}/receipt` | permission `billing:read` | receipt json |
| GET | `/api/payments/{payment_id}/receipt/pdf` | permission `billing:read` | receipt pdf |

### Discharge

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| POST | `/api/discharge/{admission_id}` | permission `discharge:create` | Discharge a patient (if still admitted), save the summary, create the final bill |
| GET | `/api/discharge/{admission_id}` | permission `discharge:read` | get summary |
| GET | `/api/discharge/{admission_id}/pdf` | permission `discharge:read` | summary pdf |

### Dashboard & analytics

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/dashboard` | any signed-in user | One endpoint, a DIFFERENT dashboard per role (decided on the server from the token - the |
| GET | `/api/analytics/patient-registrations` | permission `analytics:registrations` | chart registrations |
| GET | `/api/analytics/department-patients` | permission `analytics:departments` | chart departments |
| GET | `/api/analytics/bed-occupancy` | permission `analytics:beds` | chart beds |
| GET | `/api/analytics/emergency-cases` | permission `analytics:emergency` | chart emergency |
| GET | `/api/analytics/monthly-revenue` | permission `analytics:revenue` | chart revenue |
| GET | `/api/analytics/lab-statistics` | permission `analytics:lab` | chart lab |
| GET | `/api/analytics/medicine-consumption` | permission `analytics:medicine` | chart medicine |

### Reports

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/reports` | any signed-in user | The reports THIS role may run, with the parameters each accepts |
| GET | `/api/reports/<report_type>` | any signed-in user | Query: format=json/csv/xlsx/pdf (default json) |

### Notifications

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/notifications` | any signed-in user | Query: unread=true, type=<lab_result/low_stock/medicine_expiry/payment_pending/patient_discharge>, |
| GET | `/api/notifications/unread-count` | any signed-in user | Cheap endpoint for the bell badge - safe to poll every 30-60 seconds |
| POST | `/api/notifications/{notification_id}/read` | any signed-in user | mark read |
| POST | `/api/notifications/read-all` | any signed-in user | mark all read |
| POST | `/api/notifications/refresh` | admin | Admin: re-check stock, expiry and payment alerts right now (normally automatic) |

### Audit log (admin)

| Method | Path | Who can use it | What it does |
|---|---|---|---|
| GET | `/api/audit-logs` | admin | Query: user_id, username, role, action, entity_type, entity_id, q (search description), |
| GET | `/api/audit-logs/actions` | admin | Distinct action names, for a filter drop-down |

## Notes that are easy to miss

* **Doctor + lab orders / prescriptions:** the signed-in user must have a doctor profile (a login with role `doctor` is not enough — add it under *Doctors → Add doctor*).
* **Billing staff** do not have access to patient records; they create a bill with `patient_code` (e.g. `P2026000001`) instead of searching for the patient.
* **Medicines list** (`GET /api/pharmacy/medicines`) is open to doctors (to prescribe) and pharmacists; stock changes stay with pharmacist/admin.
* **Emergency queue:** `GET /api/triage/queue` lists only patients still *waiting*. Use `GET /api/triage` to see every case (the website does this).
* **Timetables:** `POST /api/doctors/{id}/schedule` adds a block; there is no endpoint to delete one yet.
