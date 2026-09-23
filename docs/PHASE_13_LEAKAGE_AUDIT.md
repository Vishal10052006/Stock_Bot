# Phase 13 — Leakage & Bias Audit

## Objective

Phase 13 is the integrity gate between realistic backtesting and unseen-data
evaluation. It verifies that the frozen training/evaluation dataset cannot
expose future outcome information to the predictor and that historical replay
remains causally ordered.

## Implemented boundary

backtesting.leakage_audit.audit_training_dataset checks:
- required decision schema;
- valid timezone-normalized decision timestamps;
- unique symbol/timestamp decisions;
- per-symbol chronology;
- future-looking feature names;
- future-looking dataset fields outside the explicit label;
- numeric and finite model features;
- label exclusion from model features;
- optional available_at <= decision_timestamp.

backtesting.leakage_audit.audit_future_perturbation_invariance provides a
mutation-test boundary: the authoritative feature/decision pipeline can be
rerun after perturbing only future inputs, and all pre-cutoff outputs must
remain identical.

## Evidence boundary

A structural audit is not empirical proof that the complete trading system is
leakage-free. Final Phase 13 evidence must be generated from the exact frozen
historical dataset and authoritative feature/model pipeline.

If the audit fails, downstream OOS or walk-forward performance is not valid
evidence until the root cause is fixed and the evaluation is rerun.

## Status

Implementation: complete.
Empirical gate: pending the local frozen historical dataset and reproducible audit run.
The live-trading lock remains unchanged.