# STOCK_BOT Operator Dashboard — Runtime

The operator dashboard includes a read-only Stock Scanner backed by canonical Prediction → Strategy → Risk output from the real-market virtual-paper runtime.

## Snapshot

The runtime writes `paper/virtual_sessions/<session-id>/operator_snapshot.json` after each completed candle. Writes are atomic.

## Start

Run:

    python scripts/serve_operator_dashboard.py --snapshot paper/virtual_sessions/<session-id>/operator_snapshot.json

Open `http://127.0.0.1:8765/`. The dashboard polls `/api/snapshot` every two seconds.

## Safety

The scanner is observational only. The server binds to localhost by default, exposes only a read-only snapshot endpoint, and does not submit orders or mutate strategy, risk, or account state. Live broker execution remains locked.
