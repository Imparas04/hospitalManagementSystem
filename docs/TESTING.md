# Testing Guide

## Automated tests (backend)
```powershell
cd backend
.\venv\Scripts\python.exe -m pytest -q
```
Latest result of this review: **527 passed in about 70 seconds** (the tests use an in-memory SQLite database, never your MySQL data).

Why it is fast now: `TestingConfig` sets `PASSWORD_HASH_METHOD = "pbkdf2:sha256:1"`. Every test creates users, and the
real password hash (scrypt) is deliberately slow — the earlier run of 513 tests took about 13 minutes. Real servers still use scrypt.

New tests in `tests/test_hardening_and_seed.py` cover: login lockout, logout, safe CORS default, bed gender info,
the starter-data commands, and doctors looking up medicines.

## Frontend check done during the review
The website was loaded in a simulated browser (jsdom) against the real API and driven through: sign-in for all 7 roles,
every menu page for every role, and the add/edit forms (departments, doctors + timetable, wards/beds, lab tests, medicines + stock,
users, patients + history, appointments with free-slot chips + reschedule, admissions, lab workflow, prescriptions,
billing + payment, triage → bed → resolve, change password, logout). That script is not part of the repository —
please also click through the main screens yourself in a real browser.

## Manual checklist
- Start the backend; `GET /api/health` returns `ok`.
- Sign in as admin → run *seed-demo-data* → open each menu page, none shows "Could not load".
- Register a patient → book an appointment (pick a free time) → complete it → generate a bill → take a payment → download the PDF.
- Record a triage case → *Allocate bed* → *Start treatment* → *Resolve*.
- Order a lab test as a doctor → process it as a lab technician → review it as the doctor.
- Write a prescription as a doctor → issue it as a pharmacist → stock goes down.
- Sign in as each role and confirm they only see their own pages; try a wrong password 6 times (you get a wait message).
- Download a report as CSV, Excel and PDF.
When reporting a failure include the command, the error text and the endpoint; remove passwords, tokens and patient data first.
