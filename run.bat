@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or not on PATH.
  echo Install Python 3.10+ from https://www.python.org/downloads/ and try again.
  pause
  exit /b 1
)

echo Installing dependencies (idempotent)...
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies. See output above.
  pause
  exit /b 1
)

echo Starting server at http://127.0.0.1:8765 ...
echo (First launch builds a one-time cache, takes ~10 seconds.)
start "" http://127.0.0.1:8765/
cd website\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765
