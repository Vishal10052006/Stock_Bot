# STOCK_BOT Ops Center Dashboard

The repository contains a dependency-free observational/demo UI. It is retained as a local development and replay surface; it is not the V1 real-money decision authority.

## Files

- dashboard/index.html — dependency-free UI.
- dashboard/demo_snapshot.json — safe synthetic demo payload.
- docs/V1_MANUAL_REVIEW_DASHBOARD.md — current V1 human-review runtime.

## Data boundary

The Ops Center consumes the existing MonitoringRuntime dashboard JSON contract. It does not create a second monitoring engine.

The demo payload is synthetic and must never be presented as:

- live account equity;
- live portfolio exposure;
- live broker state;
- a real trade;
- a production BUY/SELL instruction.

For the actual personal real-money workflow, use the local V1 Human Review Dashboard runtime documented in docs/V1_MANUAL_REVIEW_DASHBOARD.md.

## Safety

The Ops Center cannot:

- authorize a trade;
- modify Strategy or Risk state;
- submit broker orders;
- unlock live execution;
- promote a model.

## Deployment

The Ops Center is intentionally not deployed through GitHub Pages. STOCK_BOT is a personal-use trading system, so the repository should not create a public hosted operator surface by default.

Use the local dashboard/runtime on the trading machine instead.