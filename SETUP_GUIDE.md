# Setup Guide

## Prerequisites
- Windows PowerShell (commands below are for Windows)
- Python compatible with `backend/requirements.txt`
- Git and a modern browser

## 1. Get the project
```powershell
git clone https://github.com/Imparas04/hospitalManagementSystem.git
cd hospitalManagementSystem
```

## 2. Set up the backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and replace all placeholders with secure local values. Do not commit `.env`, passwords, tokens, or real secret keys.

Start the backend:
```powershell
python run.py
```
The development server is configured for port `5000` (`http://127.0.0.1:5000`). Keep this terminal open.

If a working virtual environment is already present, activate and use it instead of creating a new one.

## 3. Start the frontend
Open a second PowerShell window:
```powershell
cd "C:\path\to\hospitalManagementSystem\frontend"
py -m http.server 8000
```
Open `http://localhost:8000` in your browser. This is a static-file server; use the project's configured frontend workflow if one is added later.

## 4. Stop
Press `Ctrl+C` in each server terminal.

## Troubleshooting
- **Requirements file not found:** make sure the terminal is inside `backend` and the filename is `requirements.txt`.
- **401 Unauthorized:** check login/authentication, token forwarding, and the user's permissions. Do not remove authorization checks as a workaround.
- **404 Not Found:** compare the frontend URL and HTTP method with routes in `backend/app/routes/`.
- **Frontend uses mock data:** inspect `frontend/js/api.js` and the project's intended mock-mode setting.
- **Port in use:** stop the other process or configure the backend and frontend consistently.

## Security
Never commit `.env` or real credentials. Do not use Flask's development server for production. Do not include real patient information in screenshots, logs, or public issues.
