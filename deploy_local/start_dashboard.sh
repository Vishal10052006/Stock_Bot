#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
SESSION_ID="${STOCK_BOT_SESSION_ID:-LOCAL-PAPER}"
SNAPSHOT="${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}/sessions/$SESSION_ID/operator_snapshot.json"
if [[ ! -f "$SNAPSHOT" ]]; then SNAPSHOT="paper/virtual_sessions/$SESSION_ID/operator_snapshot.json"; fi
nohup python scripts/serve_operator_dashboard.py --snapshot "$SNAPSHOT" --host "${STOCK_BOT_DASHBOARD_HOST:-127.0.0.1}" --port "${STOCK_BOT_DASHBOARD_PORT:-8765}" >"${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}/logs/dashboard.log" 2>&1 &
echo $! >"${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}/pids/dashboard.pid"
echo "Dashboard: http://${STOCK_BOT_DASHBOARD_HOST:-127.0.0.1}:${STOCK_BOT_DASHBOARD_PORT:-8765}/"
