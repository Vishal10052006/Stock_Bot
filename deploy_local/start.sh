#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .venv/bin/activate ]] && source .venv/bin/activate
RUNTIME_ROOT="${STOCK_BOT_RUNTIME_ROOT:-.stock_bot_runtime}"
mkdir -p "$RUNTIME_ROOT/logs" "$RUNTIME_ROOT/pids" "$RUNTIME_ROOT/state"
MODE="${1:-paper}";LOG_FILE="$RUNTIME_ROOT/logs/$MODE.log";PID_FILE="$RUNTIME_ROOT/pids/$MODE.pid"
case "$MODE" in
shadow) CMD=(python main.py --mode shadow --symbol "${STOCK_BOT_SYMBOL:-RELIANCE}" --candles "${STOCK_BOT_SHADOW_CANDLES:-1}");;
paper) CMD=(python main.py --mode live-paper --symbol "${STOCK_BOT_SYMBOL:-RELIANCE}" --benchmark-symbol "${STOCK_BOT_BENCHMARK:-NIFTY50}" --model-artifact "${STOCK_BOT_MODEL_ARTIFACT:?Set STOCK_BOT_MODEL_ARTIFACT}" --model-sha256 "${STOCK_BOT_MODEL_SHA256:?Set STOCK_BOT_MODEL_SHA256}" --session-id "${STOCK_BOT_SESSION_ID:-LOCAL-PAPER-$(date +%Y%m%d-%H%M%S)}");;
*) echo 'Usage: $0 {shadow|paper}' >&2; exit 2;; esac
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then echo "already running: $(cat "$PID_FILE")"; exit 0;fi
nohup "${CMD[@]}" >>"$LOG_FILE" 2>&1 & PID=$!; echo "$PID" >"$PID_FILE"; sleep 1
kill -0 "$PID" 2>/dev/null || { echo "failed; see $LOG_FILE" >&2;rm -f "$PID_FILE";exit 1; }
echo "Started $MODE PID=$PID log=$LOG_FILE"
