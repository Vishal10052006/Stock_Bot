#!/usr/bin/env bash
set -euo pipefail

# Install user-level systemd units without root privileges.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

cat >"$SYSTEMD_DIR/stock-bot-paper.service" <<EOF
[Unit]
Description=STOCK_BOT Real-Market Virtual Paper Runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/python main.py --mode live-paper --symbol \${STOCK_BOT_SYMBOL} --benchmark-symbol \${STOCK_BOT_BENCHMARK} --model-artifact \${STOCK_BOT_MODEL_ARTIFACT} --model-sha256 \${STOCK_BOT_MODEL_SHA256} --session-id \${STOCK_BOT_SESSION_ID}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

cat >"$SYSTEMD_DIR/stock-bot-dashboard.service" <<EOF
[Unit]
Description=STOCK_BOT Local Read-only Dashboard
After=stock-bot-paper.service

[Service]
Type=simple
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/.env
ExecStart=$ROOT/.venv/bin/python scripts/serve_operator_dashboard.py --snapshot $ROOT/paper/virtual_sessions/\${STOCK_BOT_SESSION_ID}/operator_snapshot.json --host \${STOCK_BOT_DASHBOARD_HOST} --port \${STOCK_BOT_DASHBOARD_PORT}
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable stock-bot-paper.service stock-bot-dashboard.service

echo "User services installed."
echo "Start paper: systemctl --user start stock-bot-paper.service"
echo "Start dashboard: systemctl --user start stock-bot-dashboard.service"
