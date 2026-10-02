#!/usr/bin/env bash
set -euo pipefail
PID_DIR="${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}/pids";[[ -d "$PID_DIR" ]] || exit 0
for f in "$PID_DIR"/*.pid;do [[ -e "$f" ]] || continue;pid="$(cat "$f")";[[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && kill "$pid" 2>/dev/null || true;rm -f "$f";done
