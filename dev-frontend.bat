@echo off
REM Optional: run the React frontend in live-reload dev mode (needs Node.js 18+).
REM The production app does NOT need this -- run.bat already serves a built UI.
REM Use this only if you want to edit the frontend and see changes instantly.
setlocal
cd /d "%~dp0frontend"
where npm >nul 2>nul || ( echo [ERROR] Node.js/npm not found. Install from https://nodejs.org & pause & exit /b 1 )
if not exist "node_modules" (
  echo Installing frontend dependencies...
  call npm install
)
if not exist ".env" copy ".env.example" ".env" >nul
echo Starting Vite dev server at http://localhost:5173 (proxies /api to :8000)
call npm run dev
pause
