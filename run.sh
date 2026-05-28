#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed or not on PATH."
  echo "Install Python 3.10+ from https://www.python.org/downloads/ and try again."
  exit 1
fi

echo "Installing dependencies (idempotent)..."
python3 -m pip install --quiet -r requirements.txt

URL="http://127.0.0.1:8765/"
echo "Starting server at $URL"
echo "(First launch builds a one-time cache, takes ~10 seconds.)"

# Open the browser shortly after the server begins listening.
(
  sleep 4
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  elif command -v open >/dev/null 2>&1; then open "$URL"
  fi
) &

cd website/backend
exec python3 -m uvicorn main:app --host 127.0.0.1 --port 8765
