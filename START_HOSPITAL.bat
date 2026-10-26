@echo off
setlocal
cd /d "%~dp0"
if not exist "backend\.env" (
  echo Missing backend\.env. Copy backend\.env.example to backend\.env and fill in MySQL and JWT_SECRET_KEY first.
  pause
  exit /b 1
)
if not exist "backend\venv\Scripts\python.exe" (
  echo Missing virtual environment. Run inside backend: py -m venv venv ^&^& venv\Scripts\activate ^&^& pip install -r requirements.txt
  pause
  exit /b 1
)
start "Smart Hospital Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate && python run.py"
start "Smart Hospital Frontend" cmd /k "cd /d "%~dp0frontend" && py -m http.server 8080"
timeout /t 3 >nul
start http://127.0.0.1:8080
