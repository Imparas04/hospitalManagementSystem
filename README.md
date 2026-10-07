# Smart Hospital Operations, Emergency & Resource Management System - Backend

**Current state: Phase 3 - Doctor, Appointment & Admission** (includes everything from Phases 1-2)

Stack: Python, Flask (REST API), MySQL, SQLAlchemy, JWT (Flask-JWT-Extended), PyMySQL, pytest.
(Pandas/NumPy/PDF libraries are added in the phases that use them - Phase 6 and 7.)

## Folder structure
```
backend/
├── app/
│   ├── __init__.py          # create_app(): builds the Flask app
│   ├── config.py            # settings read from .env
│   ├── extensions.py        # db, jwt, cors objects
│   ├── cli.py               # flask init-db / seed-roles / create-admin / seed-demo-users
│   ├── models/              # database tables as Python classes (Role, User, Patient, Doctor, Appointment, ...)
│   ├── routes/              # API endpoints (auth, users, health, patients, doctors, appointments, admissions)
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
- Audit log table arrives in Phase 7

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
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Phase roadmap
| Phase | Scope |
|---|---|
| 1 | Setup, DB foundation, users, roles, login, JWT, RBAC |
| 2 | Patient management |
| **3 (this)** | Departments, doctors, appointments, wards/beds, admissions |
| 4 | Emergency, triage, priority queue, smart bed allocation |
| 5 | Laboratory + pharmacy |
| 6 | Billing, payments, discharge, PDF |
| 7 | Dashboard, Pandas/Excel/PDF reports, notifications, audit logs |
| 8 | Advanced SQL, security, testing, final integration |
