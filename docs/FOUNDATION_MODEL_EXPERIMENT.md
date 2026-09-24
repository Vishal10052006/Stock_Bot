# Foundation Model Experiment — TimesFM

Updated: 2026-09-24

## Purpose

This stage evaluates whether a pretrained time-series foundation model can
provide useful prediction-only return forecasts under the same causal,
chronological evaluation discipline as the existing Ridge and Random Forest
baselines.

It does not authorize trades and it does not replace the current Prediction Bot
baseline automatically.

## Current research position

The first reproducible adapter targets the Google Research TimesFM 2.5
PyTorch checkpoint:

- model: `google/timesfm-2.5-200m-pytorch`
- backend: PyTorch
- parameter scale: 200M
- maximum documented context: 16,384 points
- output: point forecast plus 10 quantile slices
- quantile indices: 1=q10, 5=q50, 9=q90

The current Hugging Face model card for this checkpoint identifies the model
license as Apache-2.0. The model dependency remains optional and is never
imported or loaded at module import time.

TimesFM 3.x remains a separate experimental track. It is not wired into the
production-facing Prediction Bot path by this stage.

## Data and evaluation discipline

The experiment uses the existing return target:

- 5-minute decision bars
- 12-bar future return target
- decision-time information only
- purged expanding walk-forward evaluation
- three pre-declared folds
- 60-minute purge
- no model fitting or fine-tuning
- no final-OOS observations
- no trading decision output

The first experiment uses historical close prices only. It does not inject
future covariates or revised data.

### Session-local causal context

Each prediction uses only closes satisfying:

`same symbol AND same trading date AND timestamp < decision timestamp`

The walk-forward test fold is allowed to supply earlier *observed* rows from
the same trading session. This is sequential inference, not label leakage:
the context selector enforces the strict timestamp inequality and never reads
a future test observation for the current prediction.

The context is capped at 64 bars, with 32 bars as the minimum usable history.
This prevents overnight gaps from being silently interpreted as consecutive
5-minute observations. The fold split still protects all future observations
from entering an earlier prediction.

The TimesFM 2.5 horizon is fixed at 12 bars so that the endpoint forecast can
be compared with the existing 12-bar close-to-close return target.

### Return conversion

TimesFM forecasts prices. For each decision timestamp:

`predicted_return = forecast_price_at_bar_12 / last_observed_close - 1`

The q10 and q90 price forecasts are converted using the same last observed
close. Because the denominator is positive, interval ordering is preserved.

No conformal recalibration is applied to the foundation model in this first
zero-shot experiment. Empirical interval coverage is measured directly and
must not be interpreted as a guaranteed coverage level.

## Implementation

Run:

    python scripts/run_phase9_timesfm_walk_forward.py \
      --dataset data/research/phase9_dataset_<RUN_ID>.parquet \
      --targets data/research/phase9_return_targets_<RUN_ID>_h12.parquet \
      --out data/research/phase9_timesfm_walk_forward_<RUN_ID>.json

The script:

1. loads and validates the frozen feature/target artifacts;
2. creates the same style of purged expanding walk-forward windows;
3. loads TimesFM once;
4. constructs session-local strictly-past contexts;
5. forecasts 12 bars in batches;
6. converts the endpoint price forecast to the existing return target;
7. evaluates MAE, RMSE, directional accuracy and empirical interval coverage;
8. records skipped rows caused by insufficient causal context;
9. writes dataset/model/config provenance and SHA-256 hashes.

The output artifact is research evidence only. It is not a model registry
approval and does not authorize production use.

## Hardware and dependency gate

Run:

    python scripts/check_foundation_model_preflight.py

Then explicitly install the optional dependency only if the local environment
is suitable:

    pip install 'timesfm[torch]'

Model weights are downloaded only when
`FoundationForecastModel.load()` is explicitly called.

The verified local environment on 2026-09-24 successfully loaded the
TimesFM 2.5 checkpoint and produced:

- point shape: `(1, 12)`
- median shape: `(1, 12)`
- lower shape: `(1, 12)`
- upper shape: `(1, 12)`
- quantile shape: `(1, 12, 10)`
- finite point/lower/upper outputs

The 925 MB checkpoint download is an external environment artifact and must
not be committed to this repository.

## Required empirical gate

The foundation-model experiment is accepted only after:

1. deterministic input preparation is demonstrated;
2. no future values enter the context;
3. the forecast horizon matches the declared target;
4. point forecasts and quantile outputs pass shape/finite-value checks;
5. the model is evaluated on chronological walk-forward folds;
6. no final-OOS observations are used for model or configuration selection;
7. interval coverage is measured rather than assumed;
8. results are stored with model/version/config provenance;
9. the checkpoint license is recorded;
10. the results are reviewed against the existing Ridge/RF walk-forward evidence.

A foundation model is not promoted to production merely because it produces a
forecast or performs well on a single fold.

## Completion boundary

This stage is complete only when the implementation, tests, real-data
walk-forward artifact, provenance, and limitations are all recorded.

The next stage after this experiment is **not automatic production promotion**.
Any model change must pass the existing Prediction Bot contracts and the
Strategy boundary separately.
