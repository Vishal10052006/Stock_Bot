# Personal V1 Live-Review Runtime Validation

scripts/validate_live_review_runtime.py performs one bounded, **read-only** observation cycle.

## Checks

1. Local configuration preflight.
2. Upstox Market Data Feed V3 connection.
3. Configured symbol subscription and one canonical MarketEvent.
4. Upstox read-only account/portfolio Risk context.
5. Risk freshness and decision-time causality.
6. Upstox market-state validity, account/segment readiness, and kill-switch state.

The command reports READY_FOR_HUMAN_REVIEW only when all required observations pass.

## Safety boundary

- Broker orders: **always 0**.
- Execution authority: **HUMAN_MANUAL_BUY_SELL**.
- No BUY/SELL signal is created by this validator.
- No broker order endpoint is imported or called.
- Account financial values are not printed by the CLI.
- A failed account observation is fail-closed.
- A missing/stale/causally invalid Risk context is blocked.

## Runtime

Set the existing V1 environment required by scripts/validate_live_review_env.py and set:

STOCK_BOT_LIVE_REVIEW_SYMBOL=RELIANCE

or pass:

python scripts/validate_live_review_runtime.py --symbol RELIANCE

Optional:

STOCK_BOT_LIVE_REVIEW_MAX_WAIT_SECONDS=15

The validator requires a live market event, so run it while the Upstox market feed can deliver events. A successful result establishes only the market/account observation boundary for that instant. It does not create a trade decision, approve Risk, or certify human execution.
