# Smart Hospital Operations, Emergency & Resource Management System - Backend

**Current state: Phase 1 - Project Setup + Database + Authentication + RBAC**

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
│   ├── models/              # database tables as Python classes (Role, User)
│   ├── routes/              # API endpoints (auth, users, health)
│   ├── services/            # business logic (login, user creation)
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
`docs/API_Phase_01.md` (endpoints, headers, bodies, responses, roles, JS examples) and `postman/Hospital_Phase01.postman_collection.json`.

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
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Phase roadmap
| Phase | Scope |
|---|---|
| **1 (this)** | Setup, DB foundation, users, roles, login, JWT, RBAC |
| 2 | Patient management |
| 3 | Departments, doctors, appointments, wards/beds, admissions |
| 4 | Emergency, triage, priority queue, smart bed allocation |
| 5 | Laboratory + pharmacy |
| 6 | Billing, payments, discharge, PDF |
| 7 | Dashboard, Pandas/Excel/PDF reports, notifications, audit logs |
| 8 | Advanced SQL, security, testing, final integration |
