# V1 Manual Decision Authority

## Boundary

V1 real-market decision support is owned by `trading.live.manual_decision`.
The module consumes the existing Prediction, Strategy, and Risk authorities and
returns an auditable manual-review decision.

```text
Real Market
   -> Research
   -> Analysis
   -> Prediction
   -> Strategy
   -> Risk
   -> V1 Signal
   -> Human Review
   -> MANUAL BUY / SELL
```

## Decision-time risk context

An actionable V1 manual decision requires a
`trading.live.risk_context.LiveManualRiskContext` snapshot.

The context carries observed account, portfolio, liquidity, and system-health
state into the existing Risk Engine, including:

- available equity and day-start equity
- available cash and peak equity when known
- realized and unrealized P&L
- open positions, trades today, and gross exposure
- symbol/sector exposure and position-transition context when available
- liquidity, market-data, system-readiness, and kill-switch state
- an `as_of` timestamp and explicit source identifier

The context must be timezone-aware and fresh at the time it is observed. The
maximum age is an explicit runtime configuration value; there is no source-code
freshness default.

**No paper-account value is substituted when the context is missing or stale.**
The result becomes `RISK_CONTEXT_UNAVAILABLE` and cannot request manual BUY/SELL.

## Execution rule

- No broker client is accepted by the manual decision function.
- No order submission, modification, cancellation, or fill state is produced.
- `manual_execution_status="MANUAL_BUY_SELL_REQUIRED"` means the signal passed
  the existing Strategy/Risk boundary and requires the human operator to act.
- `trade_id` remains `None` until a separate, explicitly approved execution
  workflow exists.
- The legacy `trading.paper.canonical_paper_callback` module is now only a
  compatibility import shim.

## Runtime rule

The canonical orchestrator accepts an explicit risk-context provider. The live
runtime now builds this provider from runtime configuration and observes the
Upstox account through GET-only funds, positions, holdings, trades, profile,
kill-switch, and market-status endpoints. No account value is embedded in the
source code. If the provider is unavailable, the V1 manual decision path
remains blocked rather than using virtual paper capital.

The paper runtime may continue to exist for historical validation and testing.
It is not the authority for the V1 manual real-money decision contract.

The canonical real-market runtime is now exposed through trading.live.manual_review_runtime. It does not construct a virtual account, does not accept an initial-equity value, and does not create paper fills. It consumes the read-only Upstox risk-context provider plus an explicit RiskEngine and publishes observation-only dashboard state. The legacy paper orchestrator remains a compatibility implementation detail for the shared causal pipeline and for the historical paper path; the manual-review runtime attaches no paper engine.

## Verification

`tests/trading/test_manual_decision_authority.py` verifies that:

1. the V1 decision implementation lives outside `trading.paper`;
2. no broker/order surface is exposed;
3. synthetic account-state defaults are absent from the manual decision path;
4. stale or invalid live risk context is rejected;
5. the V1 manual-review runtime attaches no virtual/paper account.
