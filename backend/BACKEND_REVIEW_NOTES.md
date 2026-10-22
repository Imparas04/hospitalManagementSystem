# Backend review notes (Phase 7)

## What is included
- Flask REST API with role-based authentication/authorization.
- 27 SQLAlchemy models matched to the 27 tables in `database/schema.sql`.
- Dashboard, analytics, reports (JSON/CSV/XLSX/PDF), notifications, audit log, and earlier hospital workflows.
- Existing pytest suite across the backend modules.

## Change made during this review
- Hardened spreadsheet export sanitization in `app/services/report_service.py` against formula injection when a dangerous formula prefix is preceded by whitespace/control characters.
- Added a regression test in `tests/test_reports.py`.

## Verification
- All Python files passed `py_compile` syntax checks.
- The spreadsheet-sanitization function was checked against formula prefixes (`=`, `+`, `-`, `@`), whitespace-prefixed formulas, tab/CR prefixes, ordinary text, and numeric values.
- The full pytest suite could not be run in this execution environment because Flask and the other project dependencies are not installed, and package installation is blocked by unavailable network access. Run `pip install -r requirements.txt` and `pytest -v` locally before deployment.

## Run locally (Windows)
```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Configure `.env` with a MySQL database and a strong `JWT_SECRET_KEY`, then initialize/seed the database as described in `README.md`, and run:
```bat
pytest -v
python run.py
```
