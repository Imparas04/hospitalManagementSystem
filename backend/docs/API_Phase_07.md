# API Documentation - Phase 7 (Dashboards, Analytics, Reports, Notifications, Audit Log)

Adds to Phases 1-6. Same conventions: `Authorization: Bearer <token>`, same success/error shape and status codes.

> **All timestamps in every API are UTC** (e.g. `"2026-10-15T04:53:46"`, no timezone suffix). Convert to local time in the browser:
> `new Date(ts + "Z").toLocaleString()`. "Today", "this month" and per-day chart buckets are calculated in the
> **hospital's timezone** (`HOSPITAL_TIMEZONE` in `.env`, default `Asia/Kolkata`), so a payment at 1 AM IST counts for the new Indian day.

---

# 1. DASHBOARD  (one endpoint, a different dashboard per role)

`GET /api/dashboard` - Auth: **any logged-in user**

The server decides what you see from your token; the frontend cannot ask for another role's numbers.
```json
{
  "role": "billing_staff", "date": "2026-10-15", "generated_at": "2026-10-15T04:53:47",
  "cards": [
    {"key": "today_revenue", "label": "Today's Revenue", "value": 1000.0, "format": "currency"},
    {"key": "unpaid_bills",  "label": "Unpaid / Part-Paid Bills", "value": 1, "format": "number"}
  ],
  "stats": {"today_revenue": 1000.0, "unpaid_bills": 1}
}
```
**Frontend tip:** render `cards` with one generic component (`format: "currency"` -> show `Rs.`), no per-role code needed.

| Role | Cards (`key`) |
|---|---|
| admin | `total_patients`, `today_appointments`, `available_beds`, `occupied_beds`, `emergency_patients`, `pending_lab_tests`, `low_stock_medicines`, `today_revenue` (+ `today_appointments_by_status`) |
| receptionist | `today_appointments`, `waiting_list`, `patients_registered_today`, `current_admissions`, `available_beds` |
| doctor | `my_appointments_today`, `my_upcoming_appointments` (next 7 days), `lab_results_to_review`, `my_admitted_patients`, `emergency_queue_waiting` |
| nurse | `emergency_waiting`, `critical_waiting`, `admitted_patients`, `available_beds`, `occupied_beds`, `beds_in_maintenance` |
| lab_technician | `pending_tests`, `awaiting_sample`, `in_processing`, `results_entered_today`, `abnormal_today` |
| pharmacist | `low_stock_medicines`, `expiring_soon_batches`, `expired_batches_with_stock`, `pending_prescriptions` |
| billing_staff | `today_revenue`, `outstanding_amount`, `unpaid_bills`, `bills_generated_today`, `payments_today` |

A doctor account with no doctor profile (Phase 3) gets zeros plus a `note`. Definitions: *emergency patients* = triage cases not yet resolved; *pending lab tests* = ordered / sample collected / processing; *low stock* = usable (non-expired) units below the reorder level; cancelled appointments are not counted.

---

# 2. ANALYTICS (Chart.js-ready)

`GET /api/analytics/<chart>` - every chart returns the **same shape**:
```json
{"title": "Patient registrations - last 7 days", "chart_type": "line",
 "labels": ["2026-10-09", "2026-10-10"],
 "datasets": [{"label": "New patients", "data": [0, 3], "backgroundColor": "#3b82f6", "borderColor": "#3b82f6"}]}
```
```js
const c = (await api("/analytics/monthly-revenue")).data;
new Chart(ctx, { type: c.chart_type, data: { labels: c.labels, datasets: c.datasets },
                 options: { scales: { x: { stacked: !!c.stacked }, y: { stacked: !!c.stacked } } } });
```
`stacked: true` is present on stacked bar charts. Day/month ranges are zero-filled (no gaps in the line).

| Endpoint | Chart | Params | Roles |
|---|---|---|---|
| `/analytics/patient-registrations` | line: new patients per day | `days` 1-365 (30) | admin, receptionist |
| `/analytics/department-patients` | bar: distinct patients per department | - | admin, receptionist, doctor |
| `/analytics/bed-occupancy` | stacked bar per ward + `summary.occupancy_percent` | - | admin, receptionist, nurse |
| `/analytics/emergency-cases` | stacked bar per day: critical/high/medium/low | `days` 1-365 (30) | admin, nurse, doctor |
| `/analytics/monthly-revenue` | bar: billed vs collected per month | `months` 1-24 (12) | admin, billing_staff |
| `/analytics/lab-statistics` | bar per test: ordered vs abnormal | `days` 1-365 (30) | admin, lab_technician, doctor |
| `/analytics/medicine-consumption` | bar: top medicines by units issued | `days` (30), `limit` 1-50 (10) | admin, pharmacist |

Errors: `400` (bad `days`/`months`/`limit`, with the field name in `errors`), `401`, `403`. Medicine consumption is counted by *prescription date*.

---

# 3. REPORTS (Pandas) - JSON, CSV, Excel, PDF

`GET /api/reports` -> the reports **this role** may run (with parameters and formats).
`GET /api/reports/<type>?format=json|csv|xlsx|pdf` (default `json`)

| `<type>` | Parameters | Roles |
|---|---|---|
| `daily` | `date=YYYY-MM-DD` (today) | admin |
| `weekly` | `date=` any day of the week -> Monday-Sunday | admin |
| `monthly` | `month=YYYY-MM` (this month) | admin |
| `department` | `from`, `to` (last 30 days) | admin |
| `doctor-performance` | `from`, `to` (last 30 days) | admin |
| `revenue` | `from`, `to` (last 30 days) | admin, billing_staff |
| `pharmacy` | `from`, `to` (last 30 days) | admin, pharmacist |

Max period 366 days. Errors: `400` bad date/format/range (field in `errors`), `403` wrong role, `404` unknown report.

**JSON shape** (the same data feeds every format):
```json
{"report_type": "revenue", "title": "Revenue Report", "period": {"from": "2026-09-16", "to": "2026-10-15"},
 "generated_at": "2026-10-15T04:53:47",
 "summary": [{"label": "Net billed (Rs.)", "value": 2537.5}],
 "tables": [{"name": "by_category", "title": "Billing by category", "columns": ["Category", "Lines", "Amount (Rs.)", "Share %"],
             "rows": [["bed", 1, 1500.0, 59.1]]}]}
```
**What each report contains**
- **daily / weekly / monthly:** per-day counts (new patients, appointments, admissions, discharges, emergency cases, lab tests, bills, revenue), appointment outcomes, busiest day, appointments by department, payments by method.
- **department:** per department - doctors, booked, completed, cancelled, no-show, waitlisted, completion %, unique patients, admissions.
- **doctor-performance:** per doctor - booked, completed, completion %, unique patients, lab tests ordered, prescriptions, admissions.
- **revenue:** gross billed, discounts, tax, net billed, collected, still outstanding; billing by category; collections by method (with share %); collections per day.
- **pharmacy:** stock on hand (usable vs expired, status OK/LOW/OUT OF STOCK, stock value), batches expiring within 30 days or already expired, consumption in the period.

**CSV** holds one table: the first by default, or choose with `&table=<name>` (table names are in the JSON). UTF-8 with BOM, so Excel shows names correctly.
**Excel** has a `Summary` sheet plus one sheet per table. **PDF** turns landscape automatically for wide tables.
Spreadsheet formula injection is blocked: a cell starting with `=`, `+` or `@` is prefixed with `'`.

**Downloading from the frontend** (files need the JWT header, so `<a href>` will not work - same as Phase 6 PDFs):
```js
async function download(path, filename) {
  const res = await fetch("http://localhost:5000/api" + path, { headers: { Authorization: "Bearer " + token } });
  if (!res.ok) { alert((await res.json()).message); return; }       // errors are JSON, success is the file
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(await res.blob()), download: filename });
  a.click();
}
download("/reports/revenue?format=xlsx&from=2026-10-01&to=2026-10-31", "revenue.xlsx");
```
Exports (csv/xlsx/pdf) are written to the audit log; plain JSON views are not.

---

# 4. NOTIFICATIONS

Each user sees notifications sent to them personally or to their role (admin sees all). Read state is **per user**.

| `type` | Sent to | When | Severity |
|---|---|---|---|
| `lab_result` | the ordering doctor | a result is entered | `warning` + "ABNORMAL" if abnormal, else `info` |
| `patient_discharge` | billing_staff, receptionist | a patient is discharged | info |
| `low_stock` | pharmacist | usable stock < reorder level | `warning`; `critical` if out of stock |
| `medicine_expiry` | pharmacist | a batch with stock expires within `EXPIRY_ALERT_DAYS` (30), or already expired | `warning`; `critical` if <= 7 days or expired |
| `payment_pending` | billing_staff | a bill is unpaid / part-paid (older than `PAYMENT_PENDING_AFTER_DAYS`, default 0) | info (warning after 7 days) |

*Alerts* (stock, expiry, payment) describe a **condition**: they appear when it becomes true, update their text (e.g. outstanding amount), disappear when it is fixed (restock, full payment) and **come back as unread** if the problem returns. They are re-checked automatically, at most once per `NOTIFICATION_SCAN_INTERVAL_SECONDS` (60), and never duplicated.

| Call | Auth | Purpose |
|---|---|---|
| `GET /api/notifications?unread=true&type=&severity=&page=&per_page=` | any | list (newest first). `data` = `{items, page, per_page, total, pages, unread_count}`; each item has `is_read` |
| `GET /api/notifications/unread-count` | any | `{"unread_count": 3}` - **poll this for the bell badge** (every 30-60 s) |
| `POST /api/notifications/<id>/read` | any | mark one read. `404` if it is not yours |
| `POST /api/notifications/read-all` | any | `{"marked": n}` |
| `POST /api/notifications/refresh` | admin | force an alert re-check now -> `{created, updated, resolved}` |

`type` must be one of `lab_result, low_stock, medicine_expiry, payment_pending, patient_discharge` (else `400`).

---

# 5. AUDIT LOG (admin only, read-only)

Every successful create/update/delete (POST/PUT/DELETE), every login and every **failed** login, and every report export is recorded automatically. Failed or rejected requests (400/403/404) are not logged because they changed nothing. Passwords are never logged. There is **no endpoint to edit or delete entries** (`405`).

`GET /api/audit-logs` - Auth: **admin**. Query: `user_id`, `username`, `role`, `action`, `entity_type`, `entity_id`, `q` (search the description), `date_from`, `date_to` (`YYYY-MM-DD`, local dates), `page`, `per_page` (max 100). Newest first.
```json
{"id": 41, "user_id": 3, "username": "demo_doctor", "role": "doctor", "action": "prescription.create",
 "entity_type": "Prescription", "entity_id": 1, "description": "Prescribed 1 medicine(s) to Sunita Patil",
 "ip_address": "127.0.0.1", "created_at": "2026-10-15T04:53:46"}
```
- **Full history of one record:** `?entity_type=Patient&entity_id=5` (e.g. created -> doctor assigned -> lab ordered -> result uploaded -> prescription -> discharged).
- `GET /api/audit-logs/actions` -> list of distinct action names for a filter drop-down.
- `username` and `role` are stored as a **snapshot**: history stays correct even if the user is renamed or changes role. A failed login has `user_id: null` and the attempted username.

Action names: `auth.login`, `auth.login_failed`, `auth.change_password`, `user.create|update|deactivate|reset_password`, `patient.create|update|deactivate|medical_history_add|visit_add`, `department.create|update`, `doctor.create|update|schedule_add`, `appointment.book|update|cancel|complete|no_show|promote`, `ward.create`, `bed.create|update_status`, `admission.create|discharge`, `discharge.create`, `triage.create|update_status|allocate_bed|resolve`, `lab_test.create`, `lab_order.create|update_status|result_entered|reviewed`, `medicine.create|batch_add`, `prescription.create|issue`, `bill.create|add_item|adjust`, `payment.create`, `report.export`.

Errors: `400` (bad date / number), `401`, `403` (not admin).

Postman: `postman/Hospital_Phase07.postman_collection.json`.
