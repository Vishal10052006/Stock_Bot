# STOCK_BOT — Risk Engine

## Scope

The Risk Engine is the deterministic veto layer downstream of Strategy and
upstream of Execution. It consumes a causal TradeCandidate plus
decision-time account/portfolio state.

It owns:
- risk budget;
- risk-first position sizing;
- initial target construction;
- daily loss limit;
- maximum trades per day;
- maximum open positions;
- gross exposure limit;
- liquidity block;
- symbol-duplicate block;
- kill-switch block.

It does not place broker orders or bypass execution authorization.

## Frozen research/paper limits

The defaults match TRADING_SPECIFICATION.md:
- risk per trade: 0.5% of available equity;
- daily loss limit: 1.5% of day-start equity;
- maximum trade entries/day: 5;
- maximum simultaneous positions: 3;
- maximum gross exposure: 75%;
- minimum target: 1.5R.

## Risk-first sizing

For a candidate with entry E and stop S:

stop_distance = abs(E - S)

risk_budget = available_equity * risk_per_trade

raw_quantity = risk_budget / stop_distance

The quantity is rounded down to the configured quantity step. If the resulting
quantity is zero, the Risk Engine rejects the candidate.

## Target

The initial target is deterministic:
- LONG: entry + 1.5 * stop_distance
- SHORT: entry - 1.5 * stop_distance

This is a risk-layer target, not a Strategy decision.

## Hard vetoes

The engine rejects a candidate when any hard safety condition is met. The
model or Strategy layer cannot override these conditions.

## Integration boundary

RiskEngine.evaluate() returns an immutable RiskAssessment containing the
RiskDecision plus the proposed entry, stop, target, risk budget, quantity,
and exposure.

The existing legacy evaluate_strategy_risk() gate remains available for
backward compatibility. Paper/backtest integration should migrate to the
full candidate-aware Risk Engine only after their input contracts provide the
required causal candidate and portfolio state.

## Validation

Dedicated tests cover:
- LONG risk-first sizing;
- SHORT target direction;
- daily loss;
- trade-count limit;
- open-position limit;
- gross exposure;
- liquidity;
- kill switch;
- duplicate-symbol protection;
- causal timestamp identity.
