# Setup Guide

Short version of the steps in `README.md`. Ports used everywhere: **backend 5000**, **frontend 8080**.

## 1. Get the project
```powershell
git clone https://github.com/Imparas04/hospitalManagementSystem.git
cd hospitalManagementSystem
```

## 2. Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # edit .env: DB_PASSWORD, JWT_SECRET_KEY, ADMIN_* ...
flask --app run.py init-db
flask --app run.py create-admin
flask --app run.py seed-demo-data  # starter departments, wards, beds, lab tests, medicines
python run.py                      # http://127.0.0.1:5000  (keep this window open)
```

## 3. Frontend (second window)
```powershell
cd frontend
py -m http.server 8080             # open http://127.0.0.1:8080
```
(`START_HOSPITAL.bat` in the project folder does steps 2-3 for you once `backend\.env` and `backend\venv` exist.)

## 4. Stop
Press `Ctrl+C` in each window.

## Useful commands (run inside `backend/`)
| Command | Purpose |
|---|---|
| `flask --app run.py init-db` | create all tables from the models |
| `flask --app run.py create-admin` | first admin, from the `ADMIN_*` values in `.env` |
| `flask --app run.py seed-roles` | insert the 7 roles |
| `flask --app run.py seed-demo-data` | departments, wards + beds, lab tests, medicines |
| `flask --app run.py seed-demo-users` | one demo user per role (asks for a password) |
| `flask --app run.py seed-demo-doctors` | demo doctors with timetables (asks for a password) |
| `flask --app run.py routes` | list every API route |
| `python -m pytest -q` | run the tests |

Alternative to `init-db`: run `backend/database/schema.sql` in MySQL, then `seed-roles` (or `database/seed.sql`).

## Security
Never commit `.env` or real credentials. Flask's built-in server is for development only. Do not use real patient data in screenshots, logs or issues.
