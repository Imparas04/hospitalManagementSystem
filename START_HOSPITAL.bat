@echo off
setlocal
cd /d "%~dp0"
if not exist ".env" (
  echo Missing backend\.env. Copy backend\.env.example to backend\.env and configure MySQL and JWT_SECRET_KEY first.
  pause
  exit /b 1
)
if not exist "venv\Scripts\python.exe" (
  echo Missing virtual environment. Run: py -m venv venv
  pause
  exit /b 1
)
start "Smart Hospital Backend" cmd /k "cd /d "%~dp0" && venv\Scripts\activate && python run.py"
start "Smart Hospital Frontend" cmd /k "cd /d "%~dp0frontend" && py -m http.server 8080"
timeout /t 2 >nul
start http://127.0.0.1:8080
