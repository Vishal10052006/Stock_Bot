# Phase 12 — Deterministic Backtesting Engine

## Boundary

Historical replay follows:

~~~text
Historical OHLCV
    -> StrategyEngine
    -> TradeCandidate
    -> RiskEngine
    -> ExecutionAuthorization
    -> BrokerSimulator
    -> TradeLifecycle
    -> Metrics / Report
~~~

The backtester does not create a second strategy implementation or bypass
Risk for actionable candidates.

## Entry

- Entry convention: decision-bar close.
- The final historical observation cannot open a new trade because no future
  observation exists to evaluate it.
- Risk-approved quantity is passed through unchanged to the broker simulator.

## Initial stop

The existing causal candidate policy constructs the stop from structural
support/resistance plus ATR. The candidate is built only from decision-time
fields.

## Target

Target is deterministic:

- LONG: entry + target_RR * stop_distance
- SHORT: entry - target_RR * stop_distance
- Default target R:R: 1.50

## Exit priority

For OHLC bars where both stop and target are touched, the engine uses the
conservative rule:

1. stop
2. target

This avoids assuming an intrabar path that the OHLC data does not provide.

## Partial exits

Default first-target behavior:

- close 50% of remaining quantity at target;
- move the remaining position's stop to entry;
- disable repeated target exits;
- later close the remaining quantity by stop, time exit, opposite signal, or
  end-of-data.

Entry fees and slippage are allocated proportionally across partial exits.

## Costs and fills

BrokerSimulator wraps the existing deterministic paper runtime. It does not
create a second fee/slippage/position model.

## Metrics

The existing metrics layer now includes:

- trade count
- gross/net P&L
- fees
- slippage
- win rate
- average win/loss
- profit factor
- expectancy
- maximum drawdown
- Sharpe ratio
- Sortino ratio
- exposure time
- turnover

## Risk integration

Actionable strategy decisions are materialized into TradeCandidate and sent
to the full Risk Engine. The backtester uses the Risk Engine's approved
quantity rather than silently applying a fixed position size.

The legacy AB-27 gate remains only for explicit NO_TRADE/disabled-risk
compatibility paths.

## Validation status

The Phase 12 implementation is in draft PR #26 and must pass the dedicated
backtesting suite plus the repository regression before merge.
