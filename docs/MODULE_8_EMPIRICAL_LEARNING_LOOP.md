# STOCK_BOT — Module 8 Empirical Learning Loop

## Status

**IMPLEMENTED — controlled evidence loop**

Module 8 composes the existing evidence-driven learning boundaries. It does not
create a second learning engine.

## Canonical flow

`Trade Outcome -> Experience -> Error Analysis -> Learning Evidence ->
Frozen Experiment -> BACKTEST -> LEAKAGE_AUDIT -> OOS -> WALK_FORWARD ->
PAPER -> Reproducibility -> Promotion Review -> Explicit Approval -> Monitoring`

## Repository boundaries

| Capability | Authoritative implementation |
|---|---|
| Trade outcome / decision memory | `journal/` |
| Error and pattern analysis | `analysis/` |
| Learning evidence | `learning/engine.py` |
| Experience linkage | `learning/experience.py` |
| Learning-cycle persistence | `learning/cycle_store.py` |
| Dataset provenance | `learning/self_learning_models.py`, `self_learning/dataset.py` |
| Experiment definition / registry | `experiments/`, `learning/experiment_store.py` |
| Controlled retraining | `learning/retraining.py`, `self_learning/real_dataset.py` |
| Candidate lifecycle | `self_learning/candidate_lifecycle.py` |
| Validation evidence | `learning/validation.py`, `self_learning/validation_orchestrator.py` |
| Promotion review | `learning/promotion.py` |
| Champion / rollback | `learning/champion.py`, `learning/lifecycle.py` |
| Drift investigation | `learning/drift.py` |
| End-to-end coordinator | `learning/orchestrator.py` |

## Module 8 safety contract

The learning loop is observational/research-governance infrastructure.

It must not:

- place or cancel broker orders;
- alter Strategy, Risk, or Safety hard controls;
- enable live execution;
- silently mutate production models;
- promote a model from metrics alone;
- manufacture OOS, walk-forward, paper, latency, calibration, or profitability evidence.

A losing trade is evidence for investigation, not an automatic retraining instruction.

## Empirical evidence boundary

Repository tests establish structural and causal contracts only. They do **not**
constitute empirical proof of profitability, predictive superiority, or
live-trading readiness.

Actual frozen datasets, realistic transaction costs/slippage, OOS and
walk-forward measurements, paper-trading observations, and explicit governance
evidence remain required before consequential promotion.

## Current implementation

`SelfLearningEngine.observe()` has regression coverage for:

1. valid decision/outcome linkage;
2. conversion into learning experiences;
3. immutable learning-cycle fingerprints;
4. fail-closed behavior for unlinked outcomes.

The public `learning` package exports `ExperimentPreparation` together with
the self-learning orchestration contracts.

## Verification

Targeted Module 8 tests:

`pytest -q tests/learning/test_self_learning_engine.py`

Repository regression:

`pytest -q`
