# STOCK_BOT — Module 8 Empirical Learning Loop

## Status

**COMPLETE — controlled evidence loop + integrity hardening**

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

## Final implementation state

The defined Self-Learning roadmap through **SL-26** is implemented. Subsequent work on this branch is integrity hardening of the completed contracts, not a new numbered SL phase.

### Integrity hardening completed after SL-26

- Promotion review is bound to the candidate lifecycle and parent champion version.
- Promotion decisions require distinct champion/challenger versions.
- Eligible/promoted decisions require validation evidence; blocked and rollback records may remain evidence-free.
- Candidate promotion decisions are bound to candidate identity, candidate fingerprint, challenger version, and parent champion version.
- Validation runs require unique stage identities and an explicit `PROMOTION_GATE`.
- Champion history requires fingerprints on every record and a continuous parent chain.
- Promoted decision timestamps must be ISO-8601 and timezone-aware.
- Existing Strategy, Risk, Safety, Execution, and broker authority boundaries remain unchanged.

### Verification

The repository was verified after the previous hardening checkpoint with:

- targeted Module 8 promotion/lifecycle/validation tests;
- full repository regression: **2362 passed, 2 deselected, 12 warnings**.

After the final timestamp-contract change, rerun the targeted and full commands before treating the latest commit as locally verified.
