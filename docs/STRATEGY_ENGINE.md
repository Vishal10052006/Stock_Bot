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



### S22 evaluation status

The S22 evaluation boundary is now explicit through
experiments.evaluate_experiment_record.

It validates measured experiment outputs without selecting a strategy or making a
profitability conclusion. The boundary checks:

- numeric metric integrity, including NaN rejection;
- bounded classification/rate metrics;
- non-negative count, cost, drawdown, and exposure fields;
- the legitimate infinite profit_factor representation when no losses exist;
- consistency between completed backtest trades and recorded trade metrics;
- consistency of winning and losing trade counts.

The resulting EvaluationReport records the experiment fingerprint, observation
count, available result sections, metric count, and validation issues.

S22 is measurement-integrity validation, not OOS performance evidence and not a
model-selection policy.


### S23 OOS validation status

The S23 final out-of-sample boundary is explicit through `backtesting.evaluate_oos`.

The boundary:

- creates chronological train, validation, and test partitions through the existing temporal splitter;
- passes only train + validation rows as predictor fitting context;
- passes the final test partition separately for inference;
- checks that the predictor returns exactly one prediction per test row;
- detects mutation of the supplied test partition;
- verifies that the predictor training context does not reach the test period;
- records structural train/validation/test counts and temporal boundaries.

The OOS contract is validation infrastructure, not evidence that a model is profitable or superior.
Performance conclusions require frozen experiment inputs, measured outputs, and the later
evaluation/validation stages.


### S24 walk-forward validation status

The S24 walk-forward boundary is implemented through `backtesting.walk_forward`.
It uses chronological expanding training windows, disjoint future test blocks, an explicit
purge interval before each test block, and fail-closed empty-partition checks.

The evaluator receives copies of the train/test partitions. Test-partition mutation is
detected, and training/test chronology is checked for every fold. Each window records
its actual test start, test end, train/test row counts, and purged-row count.

This is validation infrastructure only; it does not establish model superiority or
future trading performance.

### S25 failure-analysis status

The S25 boundary is implemented through `experiments.failure_analysis`.
It reports structural evidence gaps such as invalid measurements, missing result sections,
zero observations, inconclusive decisions, recorded limitations, and missing learning
metadata. It does not invent market causes or select a replacement strategy.

### S26 monitoring status

The S26 boundary is implemented through `experiments.monitoring`.
It evaluates operational error rate, stale-event rate, and optional prediction-distribution
drift against explicit thresholds. Alerts are observational only and cannot mutate models,
strategy configuration, risk controls, or execution authority.

### S27 lineage status

The S27 boundary is implemented through `experiments.lineage`.
A lineage record binds the exact experiment-definition fingerprint to the measured record
fingerprint, dataset version, code version, artifact fingerprints, and optional parent
lineage IDs. The lineage identifier is deterministic and content-derived.

### S28 controlled self-learning status

The S28 boundary is implemented through `experiments.self_learning`.
Learning changes are immutable proposals. A proposal must reference the exact source
experiment, use only fields explicitly listed in `ExperimentDefinition.allowed_change`,
and pass measurement-integrity checks before it can enter another validation experiment.

A valid proposal returns `VALIDATION_REQUIRED`; it never mutates frozen configuration and
there is no automatic promotion path in this boundary.
