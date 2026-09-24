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

Google Research released TimesFM 3.0 in August 2026 with native multivariate
forecasting and covariate support. Its default pretrained weights are currently
distributed under a separate non-commercial license and are restricted to
non-commercial, non-production use. Therefore TimesFM 3.0 is research-only for
this project at the current license state.

For the first reproducible adapter, this repository targets the TimesFM 2.5
PyTorch checkpoint because the official repository documents a 200M-parameter
model, up to 16,384 context points, and a stable TimesFM_2p5_200M_torch
forecast API. The dependency remains optional and is never imported at module
import time.

## Data and evaluation discipline

The experiment must use the existing return target:

- 5-minute decision bars
- 12-bar future return target
- decision-time information only
- chronological train/calibration/test boundaries
- the same causal feature construction already used by the baseline
  benchmark
- no final-OOS tuning

For a fair zero-shot foundation-model comparison, the first experiment should
use the historical close/return series only. It must not silently inject future
covariates or revised data.

The adapter returns:

- point forecast
- median forecast
- lower quantile
- upper quantile
- complete quantile tensor

No trade signal is emitted.

## Hardware and dependency gate

Do not download weights automatically.

Run:

    python scripts/check_foundation_model_preflight.py

Then explicitly install the optional dependency only if the local environment
is suitable:

    pip install 'timesfm[torch]'

The model weights are downloaded only when FoundationForecastModel.load()
is explicitly called.

## Required empirical gate

The foundation-model experiment is accepted only after:

1. deterministic input preparation is demonstrated;
2. no future values enter the context;
3. the forecast horizon matches the declared target;
4. point forecasts and quantile outputs pass shape/finite-value checks;
5. the model is evaluated on the same chronological protocol as the baselines;
6. no final-OOS observations are used for model or configuration selection;
7. interval coverage is measured rather than assumed from the model output;
8. results are stored with model/version/config provenance;
9. any license restriction is recorded with the experiment artifact.

A foundation model is not promoted to production merely because it produces a
forecast or outperforms a single fold.

## Important limitation

TimesFM 3.0 is currently not wired into the production-facing Prediction Bot
path because its default pretrained weights are non-commercial/non-production.
If the license changes or a commercially permitted checkpoint is selected, a
separate adapter can be evaluated under the same protocol.
