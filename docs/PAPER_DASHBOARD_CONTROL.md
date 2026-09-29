# Paper Dashboard Control

The dashboard now has a local operator control plane for the real-market **paper** experiment.

## Start the operator server

From the repository root:

    PYTHONPATH=. python dashboard/server.py --symbol RELIANCE --target-trades 10

Open the URL printed by the server.

The server uses only the existing LiveModelRuntime and LivePaperEngine. It does not create a second strategy, risk, safety, or execution path.

## Controls

- **START PAPER** — creates one new paper runtime and starts the real-market feed.
- **PAUSE** — pauses prediction processing at the completed-candle boundary.
- **RESUME** — resumes a paused paper session.
- **STOP PAPER** — requests a controlled feed stop and finalizes paper evidence.
- **KILL SWITCH** — emergency-stops the feed and finalizes the paper session; broker authority remains `NONE`.

A session normally ends when the configured completed-trade target is reached or the prediction safety cap is reached.

## Safety boundary

The control API exposes no broker-order endpoint and no live-unlock operation.

The authoritative path remains:

`Market → Analysis → Prediction → Strategy → Risk → Independent Safety → Paper Execution`

The dashboard reports `broker_orders = 0` and `trading_authority = NONE`.

GitHub Pages remains a static/observational dashboard. The lifecycle buttons are active only when the local operator server is running.
