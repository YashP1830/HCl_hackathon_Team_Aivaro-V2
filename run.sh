#!/usr/bin/env bash
# AI-Powered Library & Research Assistant -- macOS/Linux runner.
# Creates a venv, installs deps, and starts the app at http://127.0.0.1:8000
set -e
cd "$(dirname "$0")/backend"

PY="python3"
command -v "$PY" >/dev/null 2>&1 || PY="python"

echo "[1/4] Using: $($PY --version)"

if [ ! -x ".venv/bin/python" ]; then
  echo "[2/4] Creating virtual environment (first run only)..."
  "$PY" -m venv .venv
else
  echo "[2/4] Virtual environment already exists."
fi

VENV_PY=".venv/bin/python"

echo "[3/4] Installing dependencies..."
"$VENV_PY" -m pip install --upgrade pip >/dev/null
"$VENV_PY" -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "    Created backend/.env from template. Add your API keys there anytime."
fi

echo "[4/4] Starting server at http://127.0.0.1:8000 (Ctrl+C to stop)"
exec "$VENV_PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
