# STOCK_BOT — Strategy Engine

## Scope

The Strategy Engine is the quantitative decision layer between Prediction and
Risk. It converts validated evidence into LONG, SHORT, or NO_TRADE.

It does not predict, perform final position sizing, override Risk, call a broker,
place an order, or bypass execution authorization.

## S0-S28 coverage

S0 architecture audit; S1 contracts; S2 baseline integration; S3 prediction
integration; S4 prediction policy; S5 regime eligibility; S6 analysis
integration; S7 research integration; S8 conflict handling; S9 entry reference
boundary; S10 stop/target boundary; S11 EV helper; S12 cost/slippage boundary;
S13 liquidity boundary; S14 configuration; S15 registry; S16 NO_TRADE taxonomy;
S17 TradeCandidate boundary; S18 Risk boundary; S19 backtest compatibility;
S20 causal validation; S21 experiments; S22 evaluation; S23 OOS; S24 walk-forward;
S25 failure analysis; S26 monitoring; S27 lineage; S28 controlled self-learning.

## Decision order

INPUT_VALIDATION -> CONTEXT_VALIDATION -> PREDICTION_VALIDATION ->
BASELINE_STRATEGY -> REGIME_FILTER -> PREDICTION_POLICY -> ANALYSIS_FILTER ->
LIQUIDITY_FILTER -> COST_FILTER -> FINAL_DECISION

## Research controls

The default configuration preserves the frozen Phase 8 deterministic baseline.
Prediction thresholds and alignment rules are configurable experimental policies,
not claims of predictive superiority.

Expected value is only populated when a validated reward/loss/cost model exists.
The helper is transparent and decision-time only.

No OOS or walk-forward performance is claimed by this code. Such evidence must be
generated from frozen chronological datasets and kept separate from tuning data.

## Reused components

- trading/strategy/baseline.py
- trading/signals/*
- ml/integration/analysis_prediction.py
- intelligence/analysis/*
- market/bot/*
- backtesting/costs.py
- backtesting/fills.py
- backtesting/oos.py
- backtesting/walk_forward.py
- trading/risk/gate.py

## Self-learning

Strategy outcomes may create candidate experiments, but the Strategy Engine does
not mutate its configuration after individual losses. Any proposed change must
pass the same backtest -> OOS -> walk-forward -> paper validation pathway.

## Live boundary

The repository trading specification keeps live execution locked. This Strategy
Engine has no broker authority.


## Integration status

The authoritative StrategyEngine is now the strategy boundary used by the paper
decision loop and historical backtest engine. Both adapters preserve compatibility
with callers that still supply the frozen BaselineStrategyConfig.

The Strategy -> TradeCandidate boundary is explicit through
trading.strategy.candidate_adapter. It requires matching timestamp and symbol,
rejects NO_TRADE, and delegates causal entry/stop construction to the existing
trading.signals implementation.

The Risk gate remains downstream and consumes StrategyDecision; Strategy never
authorizes execution.


### Candidate-aware Risk integration

Actionable Strategy decisions are now materialized into the existing causal
`TradeCandidate` boundary and routed through the deterministic
`RiskEngine` before ExecutionAuthorization in both:

- `PaperDecisionLoop`
- `HistoricalBacktestEngine`

Risk-first position sizing uses the frozen ₹100,000 initial paper capital and
the configured 0.5% per-trade risk budget. Hard controls include daily loss,
trade-count, open-position, gross-exposure, liquidity, duplicate-symbol and
kill-switch rejection.

The legacy risk gate remains available as a compatibility boundary, but the
paper/backtest paths no longer use it as their primary risk authority.


### Causal validation status

S19/S20 compatibility and causal checks now include:

- public lifecycle state access instead of private backtest storage;
- future-row isolation for earlier strategy/risk decisions;
- chronological backtest processing;
- decision-time TradeCandidate stop construction;
- latest-known causal marks for open-position risk accounting;
- session-boundary reset of the daily trade counter.

These tests establish implementation-level causal invariants. They are not empirical
proof of out-of-sample trading performance; OOS and walk-forward evidence remains a
separate experimental validation stage.


### S21 experiment contract status

The first S21 boundary is now explicit through `experiments.ExperimentDefinition`.
Each experiment definition freezes:

- research question, hypothesis, and failure criterion;
- dataset and code identity;
- evaluation period and symbol universe;
- method;
- fixed parameters;
- explicitly allowed changes.

The definition has deterministic JSON serialization and a SHA-256 fingerprint so
an experiment result can be tied back to the exact specification that produced it.
This is an experiment-definition contract only; it does not constitute measured
trading performance or OOS/walk-forward evidence.
