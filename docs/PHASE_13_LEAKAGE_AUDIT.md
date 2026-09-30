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
- numeric model features, with explicitly declared conditionally-missing features allowed in the raw frozen dataset;
- infinite values and unexpected missing feature values are rejected;
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

## Semantic missingness contract

The raw FeatureDataset v1 may contain missing values for features that are
conditionally unavailable at decision time. The canonical contract is exposed
by `market.features.builder.CONDITIONALLY_MISSING_FEATURE_COLUMNS`.

Current conditionally-missing features are:
- opening-range distance/width features before the opening range is available;
- `retest_distance_pct` when no retest distance exists;
- sector context features when point-in-time sector membership is unavailable.

These values must remain explicit in the frozen raw dataset. They must not be
replaced with zero or future-derived values.

The ML preprocessing boundary resolves declared missing values using
training-only statistics. The leakage audit therefore rejects:
- non-numeric feature values;
- infinite values;
- missing values in features not explicitly declared conditionally missing;
- allowed-missing feature names that are not part of the feature schema.

This preserves the distinction between legitimate decision-time missingness and
an upstream feature-generation failure.
