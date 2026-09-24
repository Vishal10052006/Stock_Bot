# Prediction Bot — Completion Status

Updated: 2026-09-23

This document tracks the Prediction Bot engineering surface on
`feat/prediction-complete-model`.  "Implemented" means the software
contract exists and is covered by tests where practical; it does **not**
mean a model has demonstrated predictive or trading profitability.

## Architecture

Prediction Bot is prediction-only:

`Market/Research/Analysis -> causal features -> Prediction -> Strategy -> Risk -> Execution`

Prediction outputs are probabilities, return forecasts, multi-horizon forecasts,
and uncertainty/provenance. Trade decisions, sizing, stops, risk authorization,
and orders remain downstream.

## Engineering coverage

| Area | Status | Implementation |
|---|---|---|
| Phase 9 causal supervised classification | COMPLETE | `ml/datasets`, `ml/training`, `ml/models`, `ml/evaluation` |
| Logistic baseline | COMPLETE | `ml/models/logistic.py` |
| Random Forest benchmark | COMPLETE | `ml/models/random_forest.py` |
| Chronological calibration | COMPLETE | `ml/models/calibration.py` |
| Validation probability metrics | COMPLETE | `ml/evaluation/metrics.py` |
| Stratified OOS diagnostics | COMPLETE | `ml/evaluation/stratified.py` |
| Effective-sample diagnostics | COMPLETE | `ml/evaluation/effective_sample.py` |
| Model-neutral prediction boundary | COMPLETE | `ml/prediction/models.py` |
| Analysis -> Prediction integration | COMPLETE | `ml/integration/analysis_prediction.py` |
| Model registry metadata | COMPLETE | `ml/model_registry.py` |
| Artifact persistence + SHA-256 manifest | COMPLETE | `ml/prediction/artifacts.py` |
| File-backed model registry | COMPLETE | `ml/prediction/registry.py` |
| Return-forecast contract | COMPLETE | `ml/prediction/contracts.py` |
| Return forecasting baselines | COMPLETE | `ml/models/return_forecast.py` |
| Multi-horizon forecast contract | COMPLETE | `ml/prediction/contracts.py` |
| Chronological conformal return intervals | COMPLETE | `ml/models/return_forecast.py` |
| Uncertainty diagnostics | COMPLETE | `ml/prediction/uncertainty.py` |
| Prediction distribution drift | COMPLETE | `ml/prediction/drift.py` |\n| Feature distribution drift | COMPLETE | `ml/prediction/feature_drift.py` |\n| Prediction telemetry storage | COMPLETE | `ml/prediction/storage.py` |\n| Versioned inference boundary | COMPLETE | `ml/prediction/inference.py` |
| Regime/symbol/date robustness slices | COMPLETE | `ml/evaluation/robustness.py` |
| Purged walk-forward infrastructure | AVAILABLE/REUSED | `research/validation/walk_forward.py`, `backtesting/walk_forward.py` |
| Optional XGBoost/LightGBM adapters | COMPLETE | `ml/models/boosting.py` |
| Prediction → Strategy boundary | COMPLETE | `trading/strategy/prediction_adapter.py` + boundary tests |
| Risk/execution boundary | COMPLETE | existing downstream architecture |
| Foundation-model/TimesFM research | RESEARCH-ONLY | no dependency or model claim added |
| Explicit prediction input lineage | COMPLETE | `ml/prediction/contracts.py` + inference binding |\n| Fail-closed failure telemetry | COMPLETE | `ml/prediction/failures.py` |\n| Automatic self-learning | NOT AUTOMATIC | experiment-driven changes only |

## Return-forecast uncertainty boundary

`residual_std` is retained as a training-fit diagnostic only. It is not
treated as calibrated predictive uncertainty.

Return forecasting now also supports chronological split-conformal calibration:
a model is fitted on an earlier training partition, absolute residuals are
measured on a later calibration partition, and the resulting empirical radius
can produce prediction intervals. The final external test partition must remain
untouched.

## Real-data gate

The canonical Phase 9 real-data build is reproducible and uses PIT universe
membership, Upstox market data, causal 5-minute context, and explicit missing
sector coverage. The latest persisted build is:

`data/research/phase9_dataset_20260923T154216Z.parquet`

with 5,308 decision rows and 55 symbols across five decision dates.

The latest benchmark established that the pipeline reaches model evaluation,
but its experiment JSON initially required a serialization fix for nested
NumPy confusion matrices. The current branch includes that fix.

The dataset also showed incomplete historical sector-index coverage for older
dates. Missing sector context is represented honestly rather than fabricated;
this remains an empirical data-coverage limitation.

## Release gate

Before merging this branch as a production-facing Prediction Bot release,
run the repository's full test suite and the real-data benchmark from a clean
environment. The external test partition must remain untouched during model
selection and calibration.

The return-forecast interval implementation is contract/test complete. A real-data\nchronological benchmark path is now implemented in\n`scripts/build_phase9_return_target_dataset.py` and\n`scripts/run_phase9_return_forecast_experiment.py`; empirical interval coverage\nremains a release-gate measurement and must be obtained from untouched OOS data.\n\nThe Prediction Bot also now has explicit feature-drift diagnostics, append-only\nprediction telemetry, and a versioned inference boundary. These components are\nobservability/integration infrastructure; they do not authorize trades or alter\nmodel parameters automatically.

No predictive accuracy, profitability, or future performance claim is made by
this status document.


## Boundary and failure hardening

The Prediction → Strategy boundary is explicitly prediction-only: the existing
Strategy Engine remains responsible for deterministic trade/no-trade direction.
Prediction probabilities do not bypass failed strategy conditions.

Prediction inference now binds each output to deterministic hashes of the
decision-time feature row and inference context. The lineage record carries the
source type/version, timestamp, symbol, feature names, and SHA-256 hashes.
Predictor-returned identifiers must exactly match the request before lineage is
created.

Rejected prediction requests have a separate append-only failure contract.
Missing/invalid inputs are recorded as failures rather than converted into
synthetic prediction values.


## Walk-forward validation

The real-data return-forecast walk-forward stage is now implemented in
`scripts/run_phase9_return_forecast_walk_forward.py`. It uses expanding
chronological training windows with an explicit purge before each future test
block. Within each fold, the latest 10% of the training observations are held
out chronologically for conformal calibration; preprocessing is fit only on the
earlier fold-training partition. Each future test block is evaluated once and
is not used for model fitting or calibration.

The walk-forward runner reports per-fold MAE, RMSE, directional accuracy,
conformal interval coverage, and a zero-return point-forecast baseline, plus
test-row-weighted aggregate diagnostics. The benchmark is empirical validation
only; it does not select a production model or authorize trades.

The existing historical sector-context coverage limitation remains visible in
the real-data benchmark. Walk-forward evaluation does not fabricate missing
sector observations or relax causal boundaries.


## Final OOS gate

The final external-test return-forecast gate is implemented in
`scripts/run_phase9_return_forecast_final_oos.py`. The protocol is frozen at
70/15/15 chronological partitions with a 60-minute purge, a 10% chronological
training calibration holdout, and 90% conformal intervals. The script records
SHA-256 fingerprints for the dataset and target artifacts and explicitly
asserts that final OOS observations are not used for preprocessing, model
fitting, calibration, hyperparameter tuning, or model-family selection.

By default the gate can report both pre-declared baseline families
descriptively. This is not a model ranking or selection step; the final OOS
artifact is evidence for the frozen protocol only.


## Ensemble layer

A deterministic Prediction Bot ensemble is now implemented in
`ml/prediction/ensemble.py`. It combines already-generated classification
probabilities or same-horizon return forecasts using explicit non-negative
weights normalized to sum to one. The ensemble is prediction-only and does
not create trade/no-trade decisions, position sizes, risk authorization, or
orders.

Classification probabilities are combined by weighted averaging. Return point
forecasts and component uncertainty diagnostics are combined by weighted
averaging. When return components contain prediction intervals, the ensemble
uses a conservative component-envelope interval (minimum lower bound and
maximum upper bound). This envelope is explicitly **not** treated as a new
conformal coverage guarantee and is not recalibrated on final OOS data.

Weights are configuration, not learned from the final OOS partition. No final
OOS observation is consumed by the ensemble implementation. Ensemble quality
must be evaluated later under the same chronological validation discipline.


## Fixed-weight ensemble validation

A real-data walk-forward benchmark for the return ensemble is implemented in
`scripts/run_phase9_return_forecast_ensemble_walk_forward.py`. The current
default is a fixed 50/50 Ridge + Random Forest weighting. The weights are
explicit configuration and are **not** learned from or optimized against the
final OOS partition.

Each fold independently fits and conformal-calibrates the two components on
chronologically earlier observations, then evaluates the fixed-weight ensemble
on the future fold. Ensemble point forecasts are weighted averages; interval
evaluation uses the conservative component-envelope interval. That envelope
does not inherit a formal conformal coverage guarantee.

The benchmark is validation evidence for the ensemble architecture. It must
not be used to retroactively tune the final OOS result.


## Foundation-model experiment

The experimental foundation-model stage now has an optional lazy TimesFM 2.5
adapter in `ml/models/foundation_forecast.py`. The adapter is prediction-only,
validates input length and finite values, checks forecast/quantile shapes, and
returns point plus quantile forecasts without creating trade decisions.

The TimesFM dependency is intentionally optional and is not imported during
normal module import. Model weights are never downloaded by tests or the
preflight script. Run `scripts/check_foundation_model_preflight.py` before an
explicit local model load.

TimesFM 3.0 is documented as research-only for the current license state: its
default pretrained weights are distributed under a non-commercial,
non-production license. It is therefore not wired into the production-facing
Prediction Bot path.

The first empirical foundation-model experiment must use the same causal
12-bar return target and chronological evaluation discipline as the existing
baselines. Final OOS observations must not be used for model/configuration
selection, and interval coverage must be measured rather than assumed.

## Final foundation-model acceptance record

The TimesFM 2.5 zero-shot causal walk-forward experiment completed on
2026-09-24. The empirical results and limitations are recorded in
`docs/FOUNDATION_MODEL_EXPERIMENT.md`, with the consolidated engineering
acceptance audit in `docs/PREDICTION_BOT_ACCEPTANCE_AUDIT.md`.

Dedicated foundation tests pass (8 tests), dedicated TimesFM walk-forward
tests pass (6 tests), and the Prediction Bot GitHub Actions workflow for the
latest foundation adapter fix completed successfully.

The foundation-model stage remains research-only. Its measured directional
accuracy and interval coverage do not justify a production-performance claim.
The final repository-wide test suite is the remaining merge gate after the
latest adapter fix.
