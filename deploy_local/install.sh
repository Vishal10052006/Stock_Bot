#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-execution.txt
python -m pip install websocket-client protobuf
mkdir -p .stock_bot_runtime/logs .stock_bot_runtime/pids .stock_bot_runtime/state
echo "STOCK_BOT local environment installed."
