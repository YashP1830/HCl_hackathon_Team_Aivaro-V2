@echo off
REM ===========================================================================
REM  AI-Powered Library & Research Assistant  --  Windows one-click runner
REM  Creates a virtual environment, installs dependencies, and starts the app.
REM  Open http://127.0.0.1:8000 in your browser once it says "running".
REM ===========================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0backend"

REM --- Find a Python launcher (py preferred, then python) ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [ERROR] Python was not found on this PC.
  echo         Install Python 3.11+ from https://www.python.org/downloads/
  echo         During setup, tick "Add Python to PATH".
  pause
  exit /b 1
)

echo [1/4] Using Python launcher: %PY%
%PY% --version

REM --- Create virtual environment on first run ---
if not exist ".venv\Scripts\python.exe" (
  echo [2/4] Creating virtual environment ^(first run only^)...
  %PY% -m venv .venv
  if errorlevel 1 ( echo [ERROR] Could not create venv. & pause & exit /b 1 )
) else (
  echo [2/4] Virtual environment already exists.
)

set "VENV_PY=.venv\Scripts\python.exe"

REM --- Install dependencies ---
echo [3/4] Installing dependencies ^(this can take a few minutes the first time^)...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] Dependency installation failed. & pause & exit /b 1 )

REM --- Create .env from template on first run ---
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo     Created backend\.env from template. Add your API keys there anytime.
)

REM --- Start the server ---
echo [4/4] Starting server at http://127.0.0.1:8000  (press Ctrl+C to stop)
start "" http://127.0.0.1:8000
"%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
