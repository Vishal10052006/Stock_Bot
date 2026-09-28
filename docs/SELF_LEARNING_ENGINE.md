# STOCK_BOT — Self-Learning Engine SL-0..SL-20

## Purpose

The Self-Learning Engine converts accumulated trading evidence into controlled,
versioned research candidates. It does not directly execute orders, change hard
risk controls, enable live trading, or silently promote models.

Canonical loop:

    Trade Outcome
        -> Experience
        -> Error Analysis
        -> Learning Evidence
        -> Hypothesis
        -> Frozen Experiment
        -> Dataset Version
        -> Controlled Retraining
        -> Validation
        -> OOS
        -> Walk-Forward
        -> Paper
        -> Promotion Review
        -> Explicit Governance Approval
        -> Champion / Challenger
        -> Monitoring
        -> Drift Investigation
        -> New Evidence

## Repository integration

The implementation reuses the existing repository boundaries:

- Phase 16: journal decision/outcome contracts.
- Phase 17: deterministic error/pattern analysis.
- Phase 18: evidence-based LearningEngine.
- Phase 19: bounded CandidateImprovementEngine.
- Phase 9: temporal training and calibration pipeline.
- Existing backtesting, leakage audit, OOS, walk-forward, and paper evidence.
- Phase 20: immutable ml.model_registry.ModelRegistry.

No second trading model pipeline or second model registry is introduced.

## Build order

### SL-0 — Audit / architecture boundary
learning/experience.py audits decision/outcome linkage and causal ordering.

### SL-1 — Journal ↔ outcome
build_trade_experience() requires an exact shared trade_id, preserves the
decision-time feature snapshot, and derives an immutable outcome context.

### SL-2 — Learning input hardening
TradeOutcomeContext validates finite economics, MAE/MFE constraints, and
provenance fields.

### SL-3 — Evidence persistence
learning/cycle_store.py provides append-only learning-cycle storage.

### SL-4 — Experiment registry
learning/experiment_store.py persists existing ExperimentDefinition,
ExperimentRecord, and LineageRecord identities.

### SL-5 — Dataset versioning
learning/dataset_store.py persists immutable dataset manifests by version.

### SL-6 — Controlled retraining
learning/retraining.py is an adapter over the existing Phase-9 trainer.
Training creates a research result only.

### SL-7 — Candidate lifecycle
Existing Phase-19 candidate contracts remain authoritative; the new orchestration
layer consumes their research-only configuration.

### SL-8 — Validation orchestration
learning/validation.py assembles explicit integrity, leakage, OOS,
walk-forward, paper, reproducibility, stratified, and effective-sample evidence.

### SL-9 — Promotion gate
learning/promotion.py fails closed unless every required validation gate passes.
Governance approval remains explicit.

### SL-10 — Champion / challenger
learning/champion.py validates the reviewed model pair and creates an immutable
champion activation record after approval.

### SL-11 — Rollback
Rollback is represented as an explicit immutable plan. Runtime model loading is
outside the learning engine.

### SL-12 — Drift investigation
learning/drift.py turns monitoring alerts into hypotheses. Drift is never an
automatic retraining trigger.

### SL-13 — End-to-end loop
learning/orchestrator.py composes evidence collection, experiment registration,
validation, and promotion-review boundaries.

## Safety boundaries

The learning engine MUST NOT:

- place orders;
- change Risk Engine limits;
- change kill-switch behavior;
- enable live trading;
- change broker permissions;
- modify credentials;
- bypass Strategy or Risk;
- automatically promote after a metric increase;
- automatically retrain because of a single loss or recent negative P&L.

## Model-learning policy

A model/strategy change must follow:

    Observation
        -> Investigation
        -> Hypothesis
        -> Controlled Experiment
        -> Validation
        -> OOS
        -> Walk-Forward
        -> Paper
        -> Promotion Review
        -> Explicit Governance Approval

A negative or inconclusive result is a valid research result.

## Required human action

No live trading is enabled by this branch. Human approval remains required for
the final consequential promotion/live-deployment decision, and broker/API
authorization remains outside the repository learning engine.

## Validation command

Run locally from the repository root:

    python -m pytest tests/learning tests/ml tests/experiments tests/candidate_improvement -q

Then run the complete regression suite:

    python -m pytest -q

The environment with the repository checkout must execute these tests; the
GitHub connector itself does not expose a local Python runtime for this branch.
