# Prediction Bot — Final Acceptance Audit

Updated: 2026-09-25

## Scope

This audit records the engineering and empirical evidence completed on
`feat/prediction-complete-model` through the experimental foundation-model
stage. It is an acceptance record for the Prediction Bot engineering surface;
it is not a profitability claim or a production-trading approval.

## Locked architecture

The Prediction Bot remains prediction-only:

`Market/Research/Analysis -> causal features -> Prediction -> Strategy -> Risk -> Execution`

Prediction outputs do not create trade/no-trade decisions, position sizing,
risk authorization, stops, or broker orders.

## Required route

The requested engineering route was completed in order:

1. CI
2. Lineage / Explainability
3. Strategy boundary
4. Failure handling
5. Full test hardening
6. Real-data return benchmark
7. Walk-forward
8. Final OOS gate
9. Fixed-weight ensemble
10. Experimental foundation model

No final-OOS observation was used by the ensemble or TimesFM experiment for
model/configuration selection.

## Foundation implementation evidence

The TimesFM 2.5 adapter is optional and lazy. It validates:

- explicit model loading;
- minimum 32-point input history;
- finite input values;
- declared forecast horizon;
- point output shape `(n_series, horizon)`;
- quantile output shape `(n_series, horizon, 10)`;
- finite model outputs;
- monotonic configured q10/q90 bounds.

A real backend batching defect in the adapter's expected-batch-size validation
was found and fixed. The caller batch size is now captured before backend
inference, and a regression test covers backend mutation of the input
container.

Latest repository commits for this fix:

- `7881a126` — preserve foundation input batch size
- `0e1c115b` — guard foundation batch-size validation

## Test evidence

Dedicated foundation adapter tests: `8 passed`

Dedicated TimesFM causal walk-forward tests: `6 passed`

GitHub Actions Prediction Bot workflow for `0e1c115b`: `completed /
success`

Final synchronized Prediction Bot branch regression:

- branch: `feat/prediction-complete-model`
- HEAD: `15823834cbfcceed548d1839f45a4d25016a56af`
- repository suite: `1418 passed, 11 warnings`
- failures: `0`
- working tree: clean after protecting local memory
- local branch synchronization: `0 ahead / 0 behind`

The full repository regression is therefore complete for the current
Prediction Bot head.

## Real-data TimesFM evidence

Dataset:
`data/research/phase9_dataset_20260923T154216Z.parquet`

Target artifact:
`data/research/phase9_return_targets_20260924T112542Z_h12.parquet`

Protocol:

- 5,308 observations
- 3 expanding walk-forward folds
- 12-bar return horizon
- 64-bar maximum session-local context
- 32-bar minimum usable context
- 60-minute purge
- 80% nominal interval
- zero-shot TimesFM 2.5
- no fine-tuning
- final OOS not used
- prediction-only

| Fold | Train | Test | Evaluated | Skipped | MAE | RMSE | Direction | 80% Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2431 | 669 | 156 | 513 | 0.00425766 | 0.00643488 | 0.4295 | 0.5000 |
| 2 | 3387 | 664 | 187 | 477 | 0.00325133 | 0.00538989 | 0.4759 | 0.6310 |
| 3 | 4351 | 654 | 629 | 25 | 0.00480048 | 0.00849919 | 0.5056 | 0.6041 |

Interpretation is deliberately limited: the experiment demonstrates that the
foundation-model path can be executed under the causal walk-forward protocol.
It does not establish a universal directional edge, calibrated 80% predictive
intervals, profitability, or production superiority over existing baselines.

The large fold-to-fold variation in usable context is itself a data/context
coverage limitation and must remain visible.

## Final locked OOS evidence

The frozen Phase 9 final external-test return-forecast gate was executed on
the real-data benchmark artifacts.

Protocol:

- 70% chronological training partition
- 15% chronological validation partition
- 15% final external OOS partition
- 60-minute purge
- 10% chronological calibration holdout within training
- 90% conformal interval confidence
- 12-bar return horizon
- final OOS excluded from preprocessing, fitting, calibration, tuning, and
  model-family selection
- both pre-declared Ridge and Random Forest families scored descriptively

Final OOS counts:

- merged observations: `7147`
- fit: `4225`
- calibration: `475`
- validation: `511`
- final OOS: `817`

Final OOS measurements:

| Model | MAE | RMSE | Direction | 90% Coverage |
|---|---:|---:|---:|---:|
| Ridge | 0.00439895 | 0.00735287 | 0.5288 | 0.8960 |
| Random Forest | 0.00505374 | 0.00828373 | 0.4492 | 0.8996 |

Artifact:

`data/research/phase9_return_forecast_final_oos_h12.json`

The final OOS artifact remains local-only. These measurements are descriptive
evaluation evidence for the frozen protocol; they do not constitute
profitability evidence, future-performance guarantees, or a model-selection
decision.

## Production disposition

TimesFM 2.5 remains **research-only** in this stage.

No production promotion, model ranking, or automatic self-learning update is
authorized by this audit.

The existing baseline/ensemble evidence remains separate from the foundation
experiment. Any future model-selection decision must use a newly declared
validation protocol and must not tune against already-scored final OOS data.

## Remaining merge gate

Before merging this Prediction Bot branch:

1. verify the protected `memory/long_term_memory.json` remains untouched by
   the Prediction Bot commits;
2. verify the generated research artifact remains local-only unless explicitly
   approved for repository storage;
3. review the final documentation diff and CI result;
4. keep the branch unmerged until those checks pass.

The complete repository regression and locked final OOS gate are now complete.

No performance or profitability claim is made by this audit.
