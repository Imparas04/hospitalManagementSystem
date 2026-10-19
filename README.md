# Smart Hospital Operations, Emergency & Resource Management System - Backend

**Current state: Phase 7 - Dashboard, Reports, Notifications & Audit Log** (includes everything from Phases 1-6)

Stack: Python, Flask (REST API), MySQL, SQLAlchemy, JWT (Flask-JWT-Extended), PyMySQL, pytest.
(ReportLab for PDFs arrived in Phase 6; Pandas/NumPy are added in Phase 7 when reports need them. `pypdf` is used only by the tests, to read generated PDFs back.)

## Folder structure
```
backend/
├── app/
│   ├── __init__.py          # create_app(): builds the Flask app
│   ├── config.py            # settings read from .env
│   ├── extensions.py        # db, jwt, cors objects
│   ├── cli.py               # flask init-db / seed-roles / create-admin / seed-demo-users
│   ├── models/              # database tables as Python classes (Role, User, Patient, Doctor, Appointment, ...)
│   ├── routes/              # API endpoints (auth, users, patients, doctors, appointments, admissions, triage, lab, pharmacy, billing, discharge, dashboard, reports, notifications, audit)
│   ├── services/            # business logic (login, user creation, patient registration, booking, admission)
│   ├── middleware/          # login_required / roles_required / permission_required + error handlers
│   └── utils/               # responses, validators, permissions map
├── database/                # schema.sql, seed.sql, queries.sql
├── docs/                    # API + testing documentation
├── postman/                 # Postman collection
├── tests/                   # pytest tests
├── run.py  requirements.txt  .env.example  .gitignore  README.md
```
Layering (easy viva answer): **route** receives request + validates -> **service** does the work -> **model** talks to DB. Routes never contain complex logic.

## Setup (Windows / Linux / Mac)

**1. Python environment**
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / Mac
pip install -r requirements.txt
```

**2. MySQL database** (MySQL 8 or MariaDB 10.5+)
```bash
mysql -u root -p < database/schema.sql     # creates hospital_db + tables
mysql -u root -p < database/seed.sql       # inserts the 7 roles
```
Create a DB user (in the mysql shell), using your own password:
```sql
CREATE USER 'hospital_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL ON hospital_db.* TO 'hospital_user'@'localhost';
```
(Alternative to schema.sql: create an empty `hospital_db`, then run `flask init-db`.)

**3. Environment file**
```bash
copy .env.example .env         # Windows   (Linux/Mac: cp .env.example .env)
```
Open `.env` and set `DB_PASSWORD`, `JWT_SECRET_KEY` (generate: `python -c "import secrets; print(secrets.token_hex(32))"`) and the `ADMIN_*` values.

**4. Create the first admin (+ optional demo users)**
```bash
set FLASK_APP=run.py           # Windows CMD  (PowerShell: $env:FLASK_APP="run.py" | Linux/Mac: export FLASK_APP=run.py)
flask create-admin
flask seed-demo-users          # asks for a password; creates demo_doctor, demo_nurse, ... (for testing)
```

**5. Run**
```bash
python run.py
```
Open http://localhost:5000/api/health -> should show `"status": "ok"`.

## Running tests
```bash
pytest -v
```
More in `docs/TESTING_Phase_01.md`.

## API documentation
- Phase 1 (auth, users, RBAC): `docs/API_Phase_01.md` + `postman/Hospital_Phase01.postman_collection.json`
- Phase 2 (patients): `docs/API_Phase_02.md` + `postman/Hospital_Phase02.postman_collection.json`
- Phase 3 (doctors, appointments, admissions): `docs/API_Phase_03.md` + `postman/Hospital_Phase03.postman_collection.json`
- Phase 4 (triage, emergency queue, smart bed allocation): `docs/API_Phase_04.md` + `postman/Hospital_Phase04.postman_collection.json`
- Phase 5 (laboratory, pharmacy, prescriptions): `docs/API_Phase_05.md` + `postman/Hospital_Phase05.postman_collection.json`
- Phase 6 (billing, payments, discharge, PDFs): `docs/API_Phase_06.md` + `postman/Hospital_Phase06.postman_collection.json`
- Phase 7 (dashboards, analytics, reports, notifications, audit log): `docs/API_Phase_07.md` + `postman/Hospital_Phase07.postman_collection.json`

## Phase 7 - what was added
- Tables: `audit_logs`, `notifications`, `notification_reads` (27 tables in total now)
- **Role-based dashboards:** `GET /api/dashboard` returns a *different* set of cards for each of the 7 roles (decided on the server from the token). Admin gets the 8 headline numbers from the requirement document
- **Chart.js-ready analytics:** 7 chart endpoints (registration trend, department-wise patients, bed occupancy, emergency cases, monthly revenue, lab statistics, medicine consumption), all in one identical shape; each role only gets the charts that belong to its work
- **Pandas reports** (`app/services/report_service.py`): daily, weekly, monthly, department, doctor performance, revenue, pharmacy. Every report = query -> DataFrame -> group/aggregate (NumPy for rates) -> one packaged structure -> JSON / CSV / Excel / PDF, so all formats show identical numbers. Exported spreadsheets are protected against formula injection
- **Notifications:** lab result ready, patient discharged (events) and low stock, medicine expiry, payment pending (alerts that appear/update/resolve by themselves, never duplicated). Read state is per user
- **Audit log:** a middleware (`app/middleware/audit.py`) records every successful write action, login, failed login and report export: who (user + role), what, which record, when, from which IP. Append-only, admin-only. A test fails if any new write endpoint is added without an audit rule
- **Timezone-correct "today":** database timestamps are UTC; dashboards and reports use `HOSPITAL_TIMEZONE` (default `Asia/Kolkata`) so a payment at 1 AM IST counts for the right day. (`tzdata` is installed because Windows has no timezone database)
- New `.env` settings: `HOSPITAL_TIMEZONE`, `EXPIRY_ALERT_DAYS`, `PAYMENT_PENDING_AFTER_DAYS`, `NOTIFICATION_SCAN_INTERVAL_SECONDS`
- Frontend notes: all timestamps are UTC; files (PDF/Excel/CSV) must be fetched with the JWT header and saved as a blob (examples in `docs/API_Phase_07.md`)

## Phase 6 - what was added
- Tables: `bills`, `bill_items`, `payments`, `discharge_summaries` (24 tables in total now). Price columns added to existing tables: `doctors.consultation_fee`, `wards.daily_charge`, `lab_tests.price`, `medicines.unit_price` (all optional, with defaults)
- **Automatic billing algorithm** (`app/services/billing_service.py`): consultation + bed + lab + medicine + other services -> subtotal -> discount -> tax -> final amount. Money uses `Decimal` (never float) rounded to 2 places; every service is billed once only (UNIQUE `source_key` in the database); medicines are billed only for what was actually issued, in rounds; bed charges are billed after discharge
- **Payments:** partial payments, multiple methods (cash/card/upi/bank_transfer/insurance), outstanding amount, overpayment blocked, one numbered receipt per payment (`R2026000001`); the bill row is locked while paying so two cashiers cannot double-collect
- **Discharge:** one doctor call frees the bed, saves the summary (diagnosis, treatment, instructions, follow-up date) and generates the final bill. The summary also shows the stay's lab reports and medicines
- **PDF generation** with ReportLab (`app/services/pdf_service.py`): invoice, payment receipt, discharge summary. User-typed text is escaped so characters like `<` and `&` cannot break a PDF
- New `.env` settings: `DEFAULT_TAX_PERCENT`, `HOSPITAL_NAME` (see `.env.example`)
- Frontend note: PDFs need the JWT header, so open them with `fetch()` + blob (example in `docs/API_Phase_06.md`)

## Phase 5 - what was added
- Tables: `lab_tests`, `lab_orders`, `lab_results`, `medicines`, `medicine_stock`, `prescriptions`, `prescription_items` (20 tables in total now)
- **Laboratory workflow:** doctor orders a test -> lab technician marks sample collected -> processing -> enters the result -> doctor reviews it (`ordered -> sample_collected -> processing -> result_entered -> reviewed`). Each step is permission-checked and out-of-order actions are rejected
- **Pharmacy:** medicine catalog + per-batch stock (batch number, expiry date, purchase quantity, available quantity)
- **Issuing algorithm (FEFO)** in `app/services/pharmacy_service.py`: issues from the batch that expires first, never from an expired batch, splits across batches, and reports a per-medicine `shortfall` when stock runs out (prescription becomes `partially_issued` and can be completed after restocking)
- **Low-stock detection:** `GET /api/pharmacy/medicines?low_stock=true` (counts non-expired stock only). Pushing this out as a notification is part of Phase 7
- Prescriptions (doctor creates, pharmacist issues) with item-level status
- Schema fix: model indexes and `schema.sql` indexes now match exactly, so `flask init-db` and `schema.sql` build identical databases

## Phase 4 - what was added
- `triage_records` table (vitals, computed priority, status, link to the admission it resulted in)
- `wards.gender_restriction` column added (NULL = mixed, else `male`/`female`) - used by smart bed allocation
- **Priority calculation algorithm** (`app/services/triage_service.py::calculate_priority`): rule-based scoring from vitals (oxygen, heart rate, blood pressure, temperature) -> `critical`/`high`/`medium`/`low`
- **Emergency queue:** `GET /api/triage/queue` - waiting patients sorted most-urgent-first
- **Smart bed allocation algorithm** (`find_bed_for_triage` / `allocate_bed_for_triage`): matches bed type (ICU/isolation/general) + ward gender restriction + availability, prefers the tightest-fitting ward, then auto-admits the patient and occupies the bed in one call
- RBAC: nurse records triage and allocates beds; doctor reads the queue and updates status; no other role has access

## Phase 3 - what was added
- `departments`, `doctors`, `doctor_schedules`, `appointments`, `wards`, `beds`, `admissions` tables (see `database/schema.sql`)
- **Doctor profile:** links an existing user (role `doctor`) to a department + specialization; weekly recurring schedule blocks (e.g. "Mon 09:00-13:00, 15-min slots")
- **Computed availability:** `GET /api/doctors/<id>/availability?date=...` works out free slots from the weekly schedule minus already-booked appointments on that date
- **Appointment booking with automatic waiting list:** booking a taken slot does not fail - the appointment is created as `waitlisted` instead (unless the caller opts out). `POST /appointments/<id>/promote` moves a waitlisted appointment into its slot once it frees up (e.g. after a cancellation)
- **Appointment lifecycle:** scheduled -> completed / cancelled / no_show, plus reschedule with conflict re-checking
- **Wards & beds:** admin sets up wards and beds; nurse/admin can mark a bed under maintenance; a bed cannot be freed except by discharging its patient
- **Admissions:** admit a patient to a specific available bed (occupies it); discharge frees the bed automatically
- Bed selection here is **manual** (reception/nursing choose the `bed_id`). Automatic *smart* bed allocation (ward type + bed type + gender + ICU/isolation + emergency priority) is Phase 4, built on this same foundation
- RBAC: admin manages departments/doctors/wards/beds; receptionist books appointments and admits patients; doctor/nurse update what's in their scope; lab/pharmacy/billing have no access to this phase's APIs

## Phase 2 - what was added
- `patients`, `medical_history`, `visit_history` tables (see `database/schema.sql`)
- Unique Patient ID generator (`P<year><6-digit sequence>`, e.g. `P2026000001`) - see `app/services/patient_service.py::generate_patient_code`. It locks the last row of the year (`with_for_update`) so two simultaneous registrations can never collide.
- Full CRUD + search/filter/pagination for patients, with soft delete
- Emergency registration: minimal fields allowed, `registration_pending` flag so reception finishes the file later
- Medical history (allergies, chronic conditions, surgeries, notes) and visit history, both tied to the patient
- RBAC: receptionist creates, receptionist/doctor update, receptionist/doctor/nurse/admin read (see the permission table in `docs/API_Phase_02.md`)

## How authentication and RBAC work (viva notes)

**Password hashing** - passwords are hashed with Werkzeug (`scrypt` + random salt). The DB stores only the hash; a hash cannot be turned back into the password, login just re-hashes the typed password and compares.

**JWT login flow**
1. `POST /api/auth/login` with username + password.
2. Server checks the hash -> creates a signed token (contains user id, role, expiry).
3. Frontend sends `Authorization: Bearer <token>` with every request.
4. Server verifies the signature and expiry; nobody can edit the token without knowing `JWT_SECRET_KEY`.

**RBAC (Role-Based Access Control)** - three decorators in `app/middleware/auth.py`:
- `@login_required` - any active logged-in user
- `@roles_required("admin")` - only listed roles
- `@permission_required("patients:create")` - any role that owns that permission

The role -> permission table lives in ONE file: `app/utils/permissions.py`. On every request the user is re-loaded from the DB, so deactivating a user or changing their role works immediately (the role inside the token is never trusted for security).

**Example:** a doctor calls `GET /api/users` -> token valid (401 passed) -> role is `doctor`, route needs `admin` -> **403**. Hiding a button in the frontend is not enough; the API itself refuses.

**SQL injection** - all queries go through SQLAlchemy (parameterised), never string-concatenated SQL.

## Security checklist done in Phase 1
- No secrets in code (`.env`, not committed) - app refuses to start without `JWT_SECRET_KEY`
- Hashed passwords, generic login error (does not reveal whether the username exists)
- Input validation with per-field errors
- Server-side RBAC, soft-delete of users, admin cannot lock own account
- JSON errors only (no HTML pages / stack traces leak)
- CORS limited to `CORS_ORIGINS` from `.env`

## Known limitations (planned later)
- No logout/token blacklist (frontend simply deletes the token; tokens expire after `JWT_EXPIRES_HOURS`)
- No login rate limiting / account lockout (can be added in Phase 8 security pass)

## Suggested Git commits
```bash
git init
git add .
git commit -m "Phase 1: project setup, MySQL config, users/roles, JWT auth, RBAC, tests, docs"
# ... after Phase 2 work:
git add .
git commit -m "Phase 2: patient management, medical/visit history, search, RBAC, tests, docs"
# ... after Phase 3 work:
git add .
git commit -m "Phase 3: doctors, appointments with waiting list, wards/beds, admissions, RBAC, tests, docs"
# ... after Phase 4 work:
git add .
git commit -m "Phase 4: triage, priority calculation, emergency queue, smart bed allocation, RBAC, tests, docs"
# ... after Phase 5 work:
git add .
git commit -m "Phase 5: laboratory workflow, pharmacy stock with FEFO issuing, prescriptions, RBAC, tests, docs"
# ... after Phase 6 work:
git add .
git commit -m "Phase 6: automatic billing, payments and receipts, discharge summary, PDF generation, RBAC, tests, docs"
# ... after Phase 7 work:
git add .
git commit -m "Phase 7: role dashboards, Chart.js analytics, Pandas reports (Excel/CSV/PDF), notifications, audit log, tests, docs"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Phase roadmap
| Phase | Scope |
|---|---|
| 1 | Setup, DB foundation, users, roles, login, JWT, RBAC |
| 2 | Patient management |
| 3 | Departments, doctors, appointments, wards/beds, admissions |
| 4 | Emergency, triage, priority queue, smart bed allocation |
| 5 | Laboratory + pharmacy |
| 6 | Billing, payments, discharge, PDF |
| **7 (this)** | Dashboard, Pandas/Excel/PDF reports, notifications, audit logs |
| 8 | Advanced SQL, security, testing, final integration |
