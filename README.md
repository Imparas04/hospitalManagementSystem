# Smart Hospital Management System

A hospital-management web application: a **Flask REST API** (MySQL) and a **plain HTML / CSS / JavaScript** frontend.
It covers the daily workflows of a hospital — patients, doctors and departments, appointments, wards and beds,
admissions and discharge, emergency triage with automatic bed allocation, laboratory, pharmacy, billing, reports,
notifications and an audit log — with role-based access for 7 kinds of staff.

```
hospitalManagementSystem/
├── backend/      Flask API  (app/ models, routes, services, utils, middleware · tests/ · database/schema.sql)
├── frontend/     Static website (index.html, css/, js/)
├── docs/         API list, database notes, testing guide, change log, phase documents + Postman collections
├── START_HOSPITAL.bat    Windows: starts backend + frontend with one double-click
└── docker-compose.yml    Optional: MySQL + backend + frontend in containers (see "Docker")
```

## Features

| Area | What you can do |
|---|---|
| Patients | Register, search, edit, medical history, visits, emergency (incomplete) registration |
| Doctors & departments | Add departments and doctors, weekly timetables, free-slot calculation |
| Appointments | Book from free slots, reschedule, complete, cancel, no-show, waiting list + promote |
| Wards & beds | Add wards and beds, gender / ICU / isolation rules, maintenance status |
| Admissions | Admit, discharge (with summary PDF), automatic bed charges |
| Emergency | Triage vitals → priority score → **smart bed allocation** → treatment → resolved |
| Laboratory | Test catalogue, order → sample → processing → result → doctor review |
| Pharmacy | Medicines, batches with expiry, prescriptions, issue (oldest expiry first) |
| Billing | Automatic bills (consultation, lab, medicine, bed days), discount/tax, payments, PDF receipts |
| Insight | Role-based dashboard + charts, reports (JSON / CSV / Excel / PDF), alerts, audit log |

## Quick start (Windows)

1. Install **Python 3.12+**, **MySQL 8** and Git.
2. Create the database (once):
   ```sql
   CREATE DATABASE hospital_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Set up the backend:
   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env          # then open .env and fill in the values
   ```
   In `.env` set `DB_PASSWORD`, `JWT_SECRET_KEY` (make one with
   `python -c "import secrets; print(secrets.token_hex(32))"`) and the `ADMIN_*` values.
4. Create the tables, the roles, your admin account and some starter data:
   ```powershell
   flask --app run.py init-db
   flask --app run.py create-admin
   flask --app run.py seed-demo-data          # departments, wards + beds, lab tests, medicines
   ```
5. Start everything: go back to the project folder and double-click **`START_HOSPITAL.bat`**
   (or run `python run.py` in `backend/` and `py -m http.server 8080` in `frontend/`),
   then open <http://127.0.0.1:8080> and sign in with the admin account.

On macOS / Linux the commands are the same, except: `python3 -m venv venv`, `source venv/bin/activate`, `cp .env.example .env`.

### Demo accounts and demo doctors (optional, for testing / viva)

```powershell
flask --app run.py seed-demo-users       # asks for a password; creates demo_doctor, demo_nurse, ... (one per role)
flask --app run.py seed-demo-doctors     # asks for a password; creates dr_sharma, dr_mehta ... with timetables
```
Both commands are safe to run again. Use them on your own computer only.

### Adding your own data from the website

Sign in as **admin** and use: *Departments → Add department*, *Doctors → Add doctor* (creates the login and the doctor
profile together, then *Timetable* to set working hours), *Wards & Beds → Add ward / Add bed*,
*Laboratory → Add lab test*, *Pharmacy → Add medicine → Add stock*, *Users → Create user*.

## Roles

| Role | Main pages |
|---|---|
| admin | everything, incl. users and the audit log |
| receptionist | patients, appointments, admissions, beds |
| doctor | patients, appointments, emergency, lab orders + review, prescriptions, discharge summaries |
| nurse | patients (read), emergency triage, beds, admissions |
| lab_technician | laboratory (samples, results) |
| pharmacist | medicines, stock, issuing prescriptions, pharmacy report |
| billing_staff | bills, payments, revenue report |

The menu only shows what a role may use, **and the server checks permissions again on every request**
(`backend/app/utils/permissions.py` is the single place that defines who can do what).

## Security notes

* Debug mode is **off** by default and the server listens on `127.0.0.1` only. Change this only through `.env`.
* `CORS_ORIGINS` lists the websites allowed to call the API (default: the local frontend). Never use `*` on a real server.
* After 5 wrong passwords (`LOGIN_MAX_ATTEMPTS`) a username must wait `LOGIN_LOCKOUT_MINUTES`. Logout makes the token unusable immediately.
  Both use memory inside one server process — fine for this project; use Redis / the database if you run several workers.
* Passwords are hashed (scrypt), the audit log records who did what, and `.env` is in `.gitignore`.
* Never commit `.env`; never put real patient data into screenshots, tests or bug reports.

## Tests

```powershell
cd backend
python -m pytest -q
```
527 automated tests (about 1 minute). See `docs/TESTING.md` for details and the manual checklist.

## Docker (optional)

Copy `backend/.env.example` to **`.env` in the project root**, fill it in, then `docker compose up --build`.
Frontend: <http://127.0.0.1:8080> · API: <http://127.0.0.1:5000/api/health>.
*(This Docker setup was written but could not be run in the environment where this project was reviewed — see `docs/CHANGELOG.md`.)*

## Troubleshooting

| Problem | What to do |
|---|---|
| Login screen says "Cannot reach the backend" | Start Flask (`python run.py` in `backend/`). The frontend expects `http://127.0.0.1:5000/api`; to change it run `localStorage.setItem('hospital_api_url','http://host:port/api')` in the browser console. |
| Browser shows a CORS error | Put the exact address of the frontend (e.g. `http://127.0.0.1:8080`) in `CORS_ORIGINS` in `.env` and restart Flask. |
| `JWT_SECRET_KEY is not set` | Copy `.env.example` to `.env` and fill it in. |
| "Too many failed login attempts" | Wait the number of minutes shown (default 15) or restart the backend. |
| Database connection error | Check `DB_*` in `.env`, that MySQL is running and `hospital_db` exists. |
| Dropdowns are empty (no doctors / beds / tests) | Add them from the admin screens, or run `flask --app run.py seed-demo-data`. |
| Port already in use | Close the other program or change `FLASK_PORT` (and the API address in the frontend). |
| Charts are blank | Chart.js is loaded from a CDN; you need an internet connection for the charts and fonts only. |
