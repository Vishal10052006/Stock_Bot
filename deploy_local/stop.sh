#!/usr/bin/env bash
set -euo pipefail
PID_DIR="${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}/pids"
[[ -d "$PID_DIR" ]] || exit 0
for PID_FILE in "$PID_DIR"/*.pid; do
  [[ -e "$PID_FILE" ]] || continue
  PID="$(cat "$PID_FILE")"
  if [[ "$PID" =~ ^[0-9]+$ ]] && kill -0 "$PID" 2>/dev/null; then kill "$PID" 2>/dev/null || true; fi
  rm -f "$PID_FILE"
done
