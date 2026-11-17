#!/usr/bin/env bash
# MBDT dev launcher: backend http://127.0.0.1:8777 + frontend http://localhost:5173
set -euo pipefail
cd "$(dirname "$0")"
command -v uv >/dev/null || { echo "error: uv not installed"; exit 1; }
command -v pnpm >/dev/null || { echo "error: pnpm not installed"; exit 1; }
[ -d node_modules ] || pnpm install
[ -f backend/.env ] || echo "warning: backend/.env not found — set MBDT_REQUESTY_API_KEY (see README)"
uv run uvicorn app:app --app-dir backend --reload --port 8777 &
BACKEND_PID=$!
pnpm dev &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null' EXIT INT TERM
echo "MBDT dev: backend :8777 | frontend :5173 (Ctrl-C stops both)"
# portable wait: `wait -n` needs bash >= 4.3 (stock macOS ships 3.2)
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
