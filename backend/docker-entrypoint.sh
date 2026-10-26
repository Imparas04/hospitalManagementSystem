#!/bin/sh
# 1) wait for MySQL  2) create tables + roles  3) create the admin (skipped if it exists)  4) start the server
set -e
python - <<'PY'
import time
from sqlalchemy import text
from app import create_app
from app.extensions import db
app = create_app()
for attempt in range(40):
    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
        print("Database is ready.")
        break
    except Exception as exc:
        print("Waiting for the database...", type(exc).__name__)
        time.sleep(3)
else:
    raise SystemExit("Database never became ready")
PY
flask --app run.py init-db
flask --app run.py seed-roles
flask --app run.py create-admin || echo "(admin already exists - continuing)"
# ONE worker with several threads: the login-lockout counters and the logout list live in memory,
# so they only work correctly inside a single process.
exec gunicorn run:app --bind 0.0.0.0:5000 --workers 1 --threads 8
