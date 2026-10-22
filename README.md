# Smart Hospital Management System

A local hospital-management web application with a Flask REST API, a
MySQL database, and a lightweight HTML/CSS/JavaScript frontend. The
system is organized around hospital workflows such as patients, doctors,
appointments, admissions, triage, laboratory work, pharmacy, billing,
reports, notifications, and the admin dashboard.

> **Project status note:** The API and database have been started
> locally, and the dashboard has been opened successfully. Individual
> screens and endpoints still need to be tested end-to-end. A registered
> route does not by itself guarantee that its feature is fully
> implemented or working.

## Contents

-   [Technology stack](#technology-stack)
-   [Project structure](#project-structure)
-   [Prerequisites](#prerequisites)
-   [Configuration](#configuration)
-   [Installation and setup on
    Windows](#installation-and-setup-on-windows)
-   [Run the application](#run-the-application)
-   [Frontend notes](#frontend-notes)
-   [API overview](#api-overview)
-   [Authentication and roles](#authentication-and-roles)
-   [Reports and exports](#reports-and-exports)
-   [Troubleshooting](#troubleshooting)
-   [Security and data safety](#security-and-data-safety)
-   [Testing checklist](#testing-checklist)

## Technology stack

### Backend

-   **Python**
-   **Flask** --- web application and REST API
-   **Flask application factory** --- app setup is handled by
    `create_app()` in `app/__init__.py`
-   **Flask-SQLAlchemy / SQLAlchemy** --- database integration and ORM
-   **PyMySQL** --- MySQL database driver (used in the configured
    database URI)
-   **Flask-JWT-Extended** --- JWT-based authentication
-   **Flask-CORS** --- browser cross-origin request handling
-   **python-dotenv** --- loads environment configuration from `.env`
-   **Pandas** --- report data-building/export workflow
-   **CSV, Excel, and PDF exporters** --- report output formats
    described in the project work log

### Database

-   **MySQL**
-   Database name used in the local configuration: `hospital_db`

### Frontend

-   HTML: `frontend/index.html`
-   CSS: `frontend/css/style.css`
-   JavaScript files include `frontend/js/api.js`, `frontend/js/app.js`,
    and `frontend/js/store.js`
-   The frontend is served as static files with Python's built-in HTTP
    server during local development. The inspected frontend folder did
    not have a `package.json`, so `npm run dev` is not the current run
    method.

## Project structure

The following is the structure observed during development; additional
files may exist.

``` text
backend/
├── app/
│   ├── __init__.py              # Flask app factory, extensions, blueprints
│   ├── config.py                # environment-based configuration
│   ├── extensions.py            # shared Flask extensions
│   ├── models/                  # database models
│   ├── routes/                  # API blueprints
│   ├── middleware/              # error handlers and audit middleware
│   └── cli.py                   # custom Flask CLI commands
├── database/                    # database-related files
├── docs/                        # project documentation
├── frontend/
│   ├── index.html
│   ├── README.md
│   ├── STATUS.md
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── api.js
│       ├── app.js
│       └── store.js
├── postman/                     # API testing resources, if present
├── tests/                       # automated tests
├── venv/                        # local virtual environment (do not commit)
├── .env                         # local secrets/configuration (do not commit)
├── .env.example                 # configuration template, if present
├── requirements.txt             # Python dependencies
└── run.py                       # local application entry point
```

## Prerequisites

Install these before setup:

1.  **Python 3.10+** (use the version supported by the project's
    installed dependencies).
2.  **MySQL Server** running locally, normally on port `3306`.
3.  **pip**, included with standard Python installations.
4.  A modern browser such as Chrome or Edge.

Check the installed versions in PowerShell:

``` powershell
python --version
python -m pip --version
mysql --version
```

If `mysql` is not recognized, MySQL may still be installed; use MySQL
Workbench or the full path to the MySQL client.

## Configuration

The backend reads settings from `.env`. Keep this file private and never
commit real passwords or secret keys.

Typical settings used by this project:

``` dotenv
DB_HOST=localhost
DB_PORT=3306
DB_NAME=hospital_db
DB_USER=hospital_user
DB_PASSWORD=YOUR_LOCAL_DATABASE_PASSWORD

JWT_SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET
JWT_EXPIRES_HOURS=8

CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000

HOSPITAL_NAME=Smart Hospital
HOSPITAL_TIMEZONE=Asia/Kolkata
DEFAULT_TAX_PERCENT=0
EXPIRY_ALERT_DAYS=30
PAYMENT_PENDING_AFTER_DAYS=0
NOTIFICATION_SCAN_INTERVAL_SECONDS=60
```

This is an **example template**, not a copy of your actual `.env`.
Replace the database password and JWT secret with your own values. Do
not share `.env` publicly.

The configuration code builds a MySQL URI from `DB_*` variables unless
`DATABASE_URL` is set. The CORS configuration reads a comma-separated
list from `CORS_ORIGINS`.

### Create the database and database user

Create the `hospital_db` database and a dedicated MySQL user using MySQL
Workbench or the MySQL command line. Example SQL (change the password
first):

``` sql
CREATE DATABASE hospital_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER 'hospital_user'@'localhost'
  IDENTIFIED BY 'REPLACE_WITH_A_STRONG_PASSWORD';

GRANT ALL PRIVILEGES ON hospital_db.*
  TO 'hospital_user'@'localhost';

FLUSH PRIVILEGES;
```

If the database or user already exists, do not run the `CREATE`
statements again. Verify the existing account and grants instead. The
password in MySQL must match `DB_PASSWORD` in `.env`.

## Installation and setup on Windows

Open **PowerShell**.

### 1. Go to the backend folder

``` powershell
cd "C:\Users\Win 11\Desktop\hospital_system\backend"
```

If your project is stored somewhere else, use that folder's path
instead.

### 2. Activate the virtual environment

If `venv` already exists:

``` powershell
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use `python -m pip` without
activating the environment, or adjust the execution policy only if you
understand your machine's policy.

### 3. Install Python dependencies

``` powershell
python -m pip install -r requirements.txt
```

Make sure the filename is exactly `requirements.txt` (not
`requirements.tx`).

### 4. Configure `.env`

Copy `.env.example` to `.env` if the project includes an example file,
then set the database credentials, JWT secret, admin setup values, and
CORS origins. If `.env` already exists, back it up before editing.

### 5. Initialize database tables

``` powershell
flask --app run.py init-db
```

The command has previously returned `Tables created.` in this
development environment. Initializing tables is not the same as loading
production data.

### 6. Seed roles and demo accounts, if needed

``` powershell
flask --app run.py seed-roles
flask --app run.py seed-demo-users
```

These commands may report `0` newly created records when the roles or
demo accounts already exist. Do not assume they reset passwords or
replace existing records.

### 7. Create an administrator, if one does not already exist

Inspect the available command options first:

``` powershell
flask --app run.py create-admin --help
```

The project's CLI description indicates that the first admin is created
from `ADMIN_*` values in `.env`; the password is not hardcoded. Set the
required admin values as documented by the CLI or `.env.example`, then
run:

``` powershell
flask --app run.py create-admin
```

If an admin already exists, verify it before creating another. Do not
put admin passwords in this README.

## Run the application

Run the backend and frontend in **two separate PowerShell windows**.

### Terminal 1 --- Flask backend

``` powershell
cd "C:\Users\Win 11\Desktop\hospital_system\backend"
.\venv\Scripts\Activate.ps1
python run.py
```

If your project has been started successfully using a different command,
continue using that working command. Keep this terminal open while using
the application.

Check the health endpoint in a browser:

-   `http://127.0.0.1:5000/api/health`

A healthy response previously observed in this project was similar to:

``` json
{
  "success": true,
  "message": "API is running",
  "data": {
    "status": "ok"
  }
}
```

### Terminal 2 --- static frontend

``` powershell
cd "C:\Users\Win 11\Desktop\hospital_system\backend\frontend"
python -m http.server 8000
```

Open this URL in the browser:

-   **Frontend:** `http://127.0.0.1:8000`
-   **Backend health check:** `http://127.0.0.1:5000/api/health`

Do not open `index.html` directly as a `file:///...` URL. Serving it
over HTTP gives the browser a normal origin and avoids common CORS
issues.

To stop either server, press `Ctrl+C` in that server's terminal.

## Frontend notes

The API helper in `frontend/js/api.js` uses this base URL by default:

``` javascript
const BASE =
  localStorage.getItem('hospital_api_url') ||
  'http://127.0.0.1:5000/api';
```

The frontend sends requests to this API. If you change the backend
address or port, update the API URL and the backend's allowed CORS
origins consistently.

The frontend folder inspected during development did not contain a
`package.json` and did not define an npm `dev` script. Therefore,
`npm run dev` is not the correct startup command for the currently
inspected frontend. Use `python -m http.server 8000` unless the frontend
is later converted to a Node-based build system.

## API overview

The following API areas/blueprints were registered in `app/__init__.py`.
Confirm exact methods, request bodies, and response formats in each
route file or by checking the routes list.

  -----------------------------------------------------------------------
  Area                                Example route / purpose
  ----------------------------------- -----------------------------------
  Health                              `GET /api/health`

  Authentication                      `POST /api/auth/login`,
                                      `GET /api/auth/me`

  Users                               `/api/users`

  Patients                            `/api/patients`

  Doctors                             `/api/doctors`

  Appointments                        `/api/appointments`

  Admissions                          `/api/admissions`

  Triage                              `/api/triage`

  Laboratory                          `/api/lab`

  Pharmacy                            `/api/pharmacy` (medicine endpoints
                                      include `/api/pharmacy/medicines`)

  Billing                             `/api/billing`

  Discharge                           `/api/discharge`

  Notifications                       `/api/notifications`

  Audit                               `/api/audit`

  Dashboard                           `/api/dashboard`

  Reports                             `/api/reports`
  -----------------------------------------------------------------------

Blueprint prefixes and exact endpoint methods can vary; use the
registered route list as the source of truth.

To list routes:

``` powershell
flask --app run.py routes
```

## Authentication and roles

The project uses JWT authentication. The login endpoint is:

``` text
POST /api/auth/login
```

The current-user endpoint is:

``` text
GET /api/auth/me
```

Protected API requests may require an access token, commonly sent in the
`Authorization` header as a Bearer token. Follow the response and
implementation in `app/routes/auth.py` and the relevant route
decorators.

Roles already observed in the database:

-   `admin`
-   `receptionist`
-   `doctor`
-   `nurse`
-   `lab_technician`
-   `pharmacist`
-   `billing_staff`

Demo usernames previously observed in the database include
`demo_receptionist`, `demo_doctor`, `demo_nurse`, `demo_lab_technician`,
`demo_pharmacist`, and `demo_billing_staff`. Their passwords are not
documented here because they must be verified from the project's setup
instructions or configured securely. An admin user was subsequently
reported as created, but the current database state should be verified
if login fails.

## Reports and exports

The reporting work log for this project describes report builders using
Pandas and exporters for CSV, Excel, and PDF. Report categories listed
include:

-   Daily, weekly, and monthly reports
-   Department-wise reports
-   Doctor performance reports
-   Revenue reports
-   Pharmacy reports

Validate exported data against the database, especially date filters and
aggregated totals. Actual report availability depends on the current
implementation and should be checked in the reporting routes and UI.

## Troubleshooting

### CORS error or `No 'Access-Control-Allow-Origin' header`

1.  Open the frontend at `http://127.0.0.1:8000`, not as a `file:///`
    URL.

2.  Make sure `.env` includes the exact frontend origin, for example:

    ``` dotenv
    CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
    ```

3.  Restart the Flask backend after changing `.env`.

4.  Use the same host consistently (`localhost` and `127.0.0.1` are
    distinct browser origins).

### `401 Unauthorized` on a protected endpoint

-   Log in through the app first.
-   Check that the login response succeeds and that the frontend sends
    the returned JWT as a Bearer token.
-   Confirm the current user has the role/permissions required by that
    endpoint.
-   Inspect the route implementation and browser Network tab. CORS and
    authentication are different problems.

### `404 Not Found` on an API endpoint

-   Run `flask --app run.py routes` and check whether the exact URL and
    HTTP method exist.
-   Compare the frontend request path in `frontend/js/api.js` with the
    registered Flask route.
-   A missing endpoint must be implemented or the frontend path
    corrected; changing CORS will not fix a 404.

### Database connection error

-   Confirm MySQL is running and listening on the configured port.
-   Confirm `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and
    `DB_PASSWORD` match the MySQL account and grants.
-   Confirm the database user has access to `hospital_db`.
-   Restart Flask after `.env` changes.

### Port 5000 or 8000 is already in use

Stop the previous server with `Ctrl+C`, or identify the process holding
the port before stopping it. Do not terminate an unknown process
blindly.

### `npm run dev` says "Missing script: dev"

The inspected frontend has no `package.json` / `dev` script. Start it
using:

``` powershell
python -m http.server 8000
```

## Security and data safety

-   Never commit `.env`, database passwords, JWT secrets, or real
    patient information.
-   Use a dedicated database user rather than MySQL's root account for
    the application.
-   Keep CORS origins limited to the frontend hosts actually in use; do
    not use `*` for a credentialed or sensitive production application.
-   Do not use demo accounts or local development secrets in production.
-   Back up the database before migrations, schema changes, or bulk data
    operations.
-   Patient and hospital records can be sensitive. Use test data while
    developing and testing.

## Testing checklist

Before demonstrating the project, verify the following in the browser
and API:

-   [ ] Backend starts without a traceback.
-   [ ] `GET /api/health` returns a healthy response.
-   [ ] Frontend loads at `http://127.0.0.1:8000`.
-   [ ] Admin login succeeds.
-   [ ] Dashboard data loads.
-   [ ] Patient list and patient actions work.
-   [ ] Doctor list and doctor actions work.
-   [ ] Appointment creation and listing work.
-   [ ] Pharmacy/medicine list and stock workflows work.
-   [ ] Admissions, triage, laboratory, billing, and discharge workflows
    work.
-   [ ] Reports can be generated and CSV/Excel/PDF exports open
    correctly.
-   [ ] Protected endpoints reject unauthenticated requests and allow
    authorized requests.
-   [ ] No unexpected `401`, `404`, `500`, or CORS errors appear in the
    browser console or Network tab.

## Useful commands

``` powershell
# Start backend
python run.py

# Check API routes
flask --app run.py routes

# Initialize database tables (do not run casually against production)
flask --app run.py init-db

# Seed roles / demo users if required
flask --app run.py seed-roles
flask --app run.py seed-demo-users

# Start frontend (run from the frontend folder)
python -m http.server 8000
```

------------------------------------------------------------------------

**Maintainer:** Update this README when routes, setup commands,
configuration variables, or frontend startup steps change. This document
records the development setup and known project structure; verify any
feature marked for testing before describing it as production-ready.
