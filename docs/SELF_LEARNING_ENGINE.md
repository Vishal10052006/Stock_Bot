# STOCK_BOT — SELF-LEARNING ENGINE SL-00..SL-25

## Objective

Build a controlled evidence-driven improvement system:

Trade Outcome -> Experience -> Error Analysis -> Dataset Version ->
Experiment -> Retraining -> Validation -> OOS -> Walk-Forward -> Paper ->
Promotion Review -> Explicit Approval -> Monitoring -> New Evidence.

The engine never places broker orders, changes Risk controls, enables live
execution, or mutates production code.

## Existing components reused

- journal/ — authoritative decision/outcome memory (Phase 16).
- analysis/ — observable failure and pattern analysis (Phase 17).
- learning/ — trading-outcome evidence (Phase 18).
- candidate_improvement/ — bounded strategy candidates (Phase 19).
- experiments/ — frozen definitions, execution, evaluation, lineage,
  paper evidence and monitoring.
- ml/datasets/ — causal training datasets.
- ml/training/ — chronological Phase-9 training.
- ml/model_registry.py — immutable model provenance/governance (Phase 20).

## SL roadmap

| SL | Capability | Implementation boundary |
|---:|---|---|
| 00 | Package integration | self_learning/ |
| 01 | Experience contract | ExperienceBundle |
| 02 | Journal/outcome linking | orchestrator requires linked trade IDs |
| 03 | Learning input hardening | typed immutable evidence |
| 04 | Experiment registry | ExperimentSpec |
| 05 | Dataset versioning | DatasetVersion |
| 06 | Controlled retraining | retraining.retrain_candidate |
| 07 | Candidate lifecycle | ModelCandidate |
| 08 | Validation orchestration | validate_candidate |
| 09 | Promotion gate | PromotionController.review |
| 10 | Champion/challenger | explicit champion/challenger versions |
| 11 | Rollback | PromotionController.rollback |
| 12 | Drift investigation | existing monitoring feeds triggers |
| 13 | End-to-end evidence cycle | SelfLearningOrchestrator |
| 14 | Reproducibility | SHA-256 fingerprints and provenance |
| 15 | Experiment memory | append-only learning ledger |
| 16 | Strategy learning | research-side candidate surfaces only |
| 17 | Risk learning | analysis only; no hard-limit mutation |
| 18 | Execution learning | slippage/fill evidence only |
| 19 | Failure injection | promotion/evidence safety tests |
| 20 | Integration gate | full repository regression |
| 21 | Real Phase-9 dataset adapter | real_dataset.py |
| 22 | Dataset provenance builder | build_phase9_dataset_version |
| 23 | Controlled candidate retraining | retrain_candidate |
| 24 | Candidate model lifecycle | CandidateLifecycleController |
| 25 | Validation evidence orchestration | ValidationOrchestrator |

## Promotion policy

A candidate must carry artifact, experiment, evaluation and lineage identities.
Required evidence stages are:

BACKTEST -> LEAKAGE_AUDIT -> OOS -> WALK_FORWARD -> PAPER.

Structural completeness makes a candidate eligible for review, not promoted.
Promotion requires explicit approval evidence. Rollback returns to a previously
verified model without retraining.

## Non-authority boundary

The Self-Learning Engine cannot:

- place or cancel orders;
- alter Risk or Safety settings;
- alter broker permissions;
- enable live trading;
- change credentials;
- directly promote from metrics;
- bypass Prediction, Strategy, Risk, or Execution.

## Data integrity

All learning records are immutable and fingerprinted. Dataset provenance
contains source, period, symbols, row count, label distribution, feature and
label versions, source fingerprints and limitations.

## Quantitative discipline

Learning experiments preserve chronological splits, train-only preprocessing,
purge/embargo where required, protected test partitions,
effective-sample-size awareness, and one-primary-variable experiment changes.

A losing trade is evidence to investigate, not an instruction to retrain.

## Human boundary

Automation may prepare evidence and candidates. Final consequential approval,
live broker authorization, credentials and account-level actions remain
human-controlled.

## Current verification state

The architecture and contracts have been implemented on this branch. Full
pytest execution still requires a repository execution environment; the
GitHub connector provides source/repository operations but not arbitrary shell
execution.


## SL-23 — Controlled Candidate Retraining

SL-23 binds an explicit TrainingDataset, immutable DatasetVersion, and
ExperimentSpec to the existing Phase-9 training engine. It supports only
the explicitly named Logistic Regression and Random Forest trainers and
returns an immutable RetrainingResult whose status remains CANDIDATE.

The retraining boundary verifies that the supplied dataset fingerprint is
present in DatasetVersion.source_fingerprints, so a dataset cannot be
trained under unrelated provenance metadata. Candidate artifact identity is
derived from the serialized fitted model state and SHA-256 hashed.

SL-23 does not select datasets, automatically retrain from losses, promote
models, mutate production models, modify risk controls, or access execution.


## SL-24 — Candidate Model Lifecycle

SL-24 converts a verified RetrainingResult into an immutable ModelCandidate,
binding dataset, experiment, artifact, evaluation, parent-model and lineage
identities. Lifecycle transitions are explicit and fail closed.

Allowed progression is CANDIDATE -> VALIDATING -> PAPER ->
PROMOTION_REVIEW. Rejection is terminal. PROMOTED can only be applied from an
explicit PROMOTION_REVIEW state using a matching PROMOTION decision; it is not
a direct lifecycle transition. PROMOTED may later transition to RETIRED.

Every candidate state is persisted through the existing append-only
LearningStore when a store is supplied. No model is deployed, broker action is
performed, risk control is changed, or Phase-20 model approval is invoked by
this lifecycle controller.


## SL-25 — Validation Evidence Orchestration

SL-25 adds `ValidationOrchestrator` and immutable `ValidationRun` records. The orchestrator binds existing `ValidationSummary` evidence to one `ModelCandidate`, requires the candidate to enter `VALIDATING`, rejects unknown or mismatched stage keys, and preserves missing-stage failures rather than treating them as passes. Required evidence remains BACKTEST, LEAKAGE_AUDIT, OOS, WALK_FORWARD, and PAPER.

The orchestrator delegates structural gating to the existing `validate_candidate()` function. A valid gate may advance the candidate from VALIDATING through PAPER to PROMOTION_REVIEW; it never creates a promotion decision, deploys a model, accesses a broker, or changes risk/execution controls. Stage evidence is supplied by existing validation boundaries rather than by a second backtest or validation engine.

