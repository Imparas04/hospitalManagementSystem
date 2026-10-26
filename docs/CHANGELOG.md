# Change Log — project review (October 2026)

## Fixed — things that blocked real use
- **Empty hospital:** a fresh database had no departments, doctors, wards, beds or lab tests and the website had no way to add them.
  Added the screens (Departments, Doctors + timetable, Wards & Beds, Lab tests, Medicines + stock, Users) and the commands
  `seed-demo-data` and `seed-demo-doctors`.
- **Doctors could not write prescriptions:** they had `prescriptions:create` but no permission to list medicines. Added `medicines:read` for doctor and pharmacist.
- **Emergency screen lost patients:** it showed `/triage/queue` (waiting cases only), so a patient with a bed could never be moved to
  "in treatment" or "resolved". It now lists all active cases.
- **Wrong columns:** emergency vitals, lab results (`[object Object]`), billing "paid", audit "record", pharmacy "strength/form" and bed
  "gender" were read from fields that do not exist. Fixed. Beds now return `gender_restriction`.
- **Users list** showed only the first 10 users. Now paged + searchable.
- **Billing staff** cannot read patients; the bill form now takes the patient ID code.

## Added — frontend
Rewritten as readable, commented files (`config.js, api.js, ui.js, pages-*.js, main.js`): role-based menu, search-as-you-type patient picker
(no more typing numeric IDs), dropdowns for doctors/beds/tests/medicines, free appointment slots, patient detail with history and visits,
admissions + discharge summary PDF, triage bed allocation, lab workflow, prescriptions, bills with items/payments/receipts,
reports with date inputs, change password, proper logout. Removed the unused `store.js` mock data.

## Added — backend
- `run.py`: debug OFF and `127.0.0.1` by default (was debug ON + `0.0.0.0`).
- CORS default is the local frontend (was `*`).
- Login lockout (`LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES`) and `POST /api/auth/logout` (token revocation).
- `.env.example` (was missing), `Dockerfile`, `docker-compose.yml`, GitHub Actions workflow.
- 14 new tests (527 total). The test run is much faster (reported 13 minutes before; about 1 minute in the review environment).

## Cleaned up
One README / `.gitignore`, one port (8080) everywhere, `START_HOSPITAL.bat` matches the real folder layout, docs moved into `docs/`,
API table generated from the code, PDF name typo fixed. `schema.sql` was compared with the models: 27 tables, identical columns.

## Known limitations (honest list)
- Login lockout and token revocation live in server memory (one process). Use Redis/DB for several workers.
- No database migrations (Alembic): schema changes need `schema.sql` / manual changes.
- Short lists (departments, doctors, beds, medicines, lab tests) are not paged.
- Timetable rows cannot be deleted (no endpoint). Patients cannot be deactivated from the website.
- Postman collections in `docs/phases/` were not updated for `/auth/logout`.
- Docker files and the CI workflow were written but not executed in the review environment.
- The website was tested in a simulated browser, not in Chrome/Firefox. Chart.js and fonts load from CDNs.
- Everything was tested on SQLite; MySQL-specific behaviour was not run here (the schema file matches the models, though).
