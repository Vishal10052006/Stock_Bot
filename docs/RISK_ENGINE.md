# STOCK_BOT — Risk Engine

## Scope

The Risk Engine is the deterministic veto layer downstream of Strategy and
upstream of Execution. It consumes a causal TradeCandidate plus decision-time
account, portfolio and optional market-risk state.

It owns:

- risk budget;
- risk-first position sizing;
- stop validation;
- minimum-R target construction;
- daily loss limit;
- maximum entries/day;
- maximum open positions;
- gross exposure limit;
- optional available-cash constraint;
- optional total-drawdown limit;
- optional symbol/sector concentration;
- optional correlation concentration;
- optional volatility-aware sizing;
- liquidity block;
- duplicate-symbol block;
- independent kill-switch state;
- machine-readable risk reason codes;
- immutable risk assessments.

It does not place broker orders or bypass execution authorization.

## Frozen research/paper limits

The defaults match TRADING_SPECIFICATION.md:

- risk per trade: 0.5% of available equity;
- daily loss limit: 1.5% of day-start equity;
- maximum trade entries/day: 5;
- maximum simultaneous positions: 3;
- maximum gross exposure: 75%;
- minimum target: 1.5R.

The specification does not freeze a numeric total-drawdown cap, so that
control remains opt-in.

These defaults are not silently changed by the Risk Engine.

## Risk-first sizing

For a candidate with entry E and stop S:

    stop_distance = abs(E - S)
    risk_budget = available_equity * risk_per_trade
    raw_quantity = risk_budget / stop_distance

The quantity is rounded down to the configured quantity step.

If the resulting quantity is zero, the Risk Engine rejects the candidate.

## Stop boundary

Causal stop construction remains upstream in
trading.signals.candidate.py. The Risk Engine does not duplicate that logic.

Risk validates:

- LONG stop < entry;
- SHORT stop > entry;
- positive finite prices;
- positive finite stop distance.

## Target

The initial target is deterministic:

- LONG: entry + target_multiple_r * stop_distance;
- SHORT: entry - target_multiple_r * stop_distance.

The frozen target_multiple_r is 1.5.

## Decision actions

RiskDecision retains the legacy APPROVED/REJECTED status for compatibility
with the execution boundary.

A separate action property exposes:

- APPROVE;
- RESIZE;
- REJECT.

RESIZE is only possible when an explicit advanced policy permits deterministic
sizing reduction. The frozen v1 configuration keeps allow_resize=False, so
gross-exposure and volatility violations remain hard NO_TRADE outcomes.

## Position transition context

Risk can consume an optional immutable `RiskPositionContext` describing the
signed position transition at decision time:

- OPEN: flat -> non-zero;
- INCREASE: larger absolute position in the same direction;
- REDUCE: smaller non-zero position in the same direction;
- FLATTEN: existing position -> flat;
- REVERSE: existing direction -> opposite direction.

The context also carries existing and projected signed quantities and validates
that the transition geometry is internally consistent.

When supplied, position-count and duplicate-symbol gates are transition-aware:
REDUCE and FLATTEN do not consume a new open-position slot or trigger the
duplicate-symbol veto. OPEN still remains subject to both controls, while
REVERSE is treated as a transition that creates a new directional position.

Risk economics now handle all three non-open transition classes explicitly. REDUCE and FLATTEN use the signed transition order quantity as exposure-release operations. REVERSE closes the existing signed position in full and risk-sizes only the newly opened directional quantity; the resulting broker order is the close quantity plus the new opening quantity. Gross exposure is calculated from the projected signed position rather than by blindly adding the full broker order value.

## Hard vetoes

The engine rejects a candidate when any hard safety condition is met:

- system not ready;
- kill switch active;
- invalid/stale market data;
- insufficient liquidity;
- daily loss limit reached;
- maximum entries reached;
- maximum open positions reached;
- duplicate symbol;
- invalid stop;
- invalid target;
- zero valid position size;
- maximum gross exposure;
- configured symbol/sector concentration limit;
- configured correlation limit;
- configured volatility limit.

The model or Strategy layer cannot override these conditions.

## Optional advanced controls

The frozen trading specification defines gross exposure but does not yet freeze
numeric symbol, sector, correlation or volatility thresholds.

Therefore these controls are opt-in configuration fields. They are not given
invented production defaults.

When a numeric policy is later frozen, it can be enabled without changing the
core Risk Engine contract.

## Independent kill switch

KillSwitchState is separate from model output and supports hard safety
conditions including:

- manual stop;
- data failure;
- broker failure;
- abnormal latency;
- position mismatch;
- invalid price;
- duplicate order;
- connectivity failure;
- model degradation.

The Risk Engine blocks new trades whenever the switch is active.

A later live execution layer must independently re-check the same safety state.

## Auditability

Every RiskDecision carries:

- timestamp;
- normalized symbol;
- strategy direction;
- risk version;
- stable reason code;
- human-readable reason;
- derived action.

RiskAssessment additionally records:

- entry;
- stop;
- target;
- risk budget;
- stop distance;
- requested quantity;
- final quantity;
- gross exposure after the trade;
- daily P&L;
- volatility factor.

## Integration boundary

RiskEngine.evaluate() returns an immutable RiskAssessment.

The Strategy -> TradeCandidate boundary remains causal and is implemented in
trading.strategy.candidate_adapter.

The Risk Engine never reads future labels and never contacts a broker.

## Validation

Dedicated tests cover:

- LONG risk-first sizing;
- SHORT target direction;
- stable reason codes;
- daily loss;
- trade-count limit;
- open-position limit;
- gross exposure;
- liquidity;
- kill switch;
- duplicate-symbol protection;
- signed position-transition context and transition-aware entry gates;
- causal timestamp identity;
- optional symbol concentration;
- optional sector concentration;
- optional correlation concentration;
- optional volatility sizing;
- deterministic resize behavior.

## Phase 11 status

Implemented in branch: phase-11-risk-engine-v1

Core v1 controls are implemented. Numeric policies for advanced
concentration/correlation/volatility controls remain intentionally opt-in
because they are not frozen by the current Trading Specification.

Next dependent phase:

Phase 12 — Backtesting Engine
