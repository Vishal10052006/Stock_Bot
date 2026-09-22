# Phase 9 — First ML Model

## Purpose

Phase 9 introduces the first supervised trading-outcome model. It consumes
the causal Phase 5 FeatureDataset and Phase 7 decision-level labels and
outputs probabilities for LONG_SUCCESS, SHORT_SUCCESS, and NO_EDGE.

The model produces probabilities only. Trade/no-trade logic belongs to the
Phase 10 Signal Decision Engine.

## Implemented architecture

OHLCV
  -> Phase 4 Indicators
  -> Phase 5 Features
  -> Phase 6 Regime
  -> Directional Research Candidates
  -> Phase 7 Decision Labels
  -> TrainingDataset v1
  -> Temporal split
  -> Training-only preprocessing
  -> Logistic Regression
  -> Chronological calibration holdout
  -> Isotonic probability calibration
  -> Validation probabilities

The external test partition remains untouched by the Phase 9 trainer.

## TrainingDataset v1

The supervised dataset contains only timestamp, symbol, frozen Phase 5
feature columns, and label.

Future outcome metadata is explicitly forbidden. The validator checks
timezone-aware timestamps, duplicate observations, chronological ordering,
valid labels, feature types, and infinite values.

## Temporal discipline

Default outer split:

- 70% train
- 15% validation
- 15% test
- 60-minute purge around split boundaries

Inside the training partition, the latest 15% of decision timestamps is
reserved for calibration. The classifier is never fitted on those calibration
observations.

No random shuffling is used.

## Models

### Logistic Regression v1

The first model is LogisticOutcomeModel.

Configuration:

- C = 1.0
- max_iter = 1000
- random_state = 42

Output order is always LONG_SUCCESS, SHORT_SUCCESS, NO_EDGE.

### Random Forest benchmark

RandomForestOutcomeModel is implemented as the first non-linear benchmark.

Default configuration:

- 300 estimators
- max depth = 8
- minimum leaf size = 5
- sqrt feature sampling
- random_state = 42

It is a benchmark model, not an automatic replacement for Logistic Regression.

## Probability calibration

The calibrated Logistic Regression path reserves a chronological calibration
holdout inside the training partition and applies one-vs-rest isotonic
regression. Calibrated probabilities are renormalized to sum to one.

Probability quality is measured with:

- log loss
- multiclass Brier score
- expected calibration error (ECE)

Classification quality is measured with:

- accuracy
- balanced accuracy
- macro precision
- macro recall
- macro F1
- confusion matrix

These metrics describe predictive quality. They do not establish trading
profitability.

## Phase 9 completion contract

Phase 9 is considered implementation-complete only when P9-00 through P9-17
are present and tested:

- P9-00 research specification and failure criteria
- P9-01 prediction input/output contract
- P9-02 training-dataset validation
- P9-03 label audit
- P9-04 temporal split and purge
- P9-05 train-only preprocessing
- P9-06 majority/class-prior/BaselineStrategy benchmark definitions
- P9-07 Logistic Regression v1
- P9-08 probability evaluation
- P9-09 classification evaluation
- P9-10 regime/symbol/date stratified evaluation
- P9-11 effective-sample-size reporting
- P9-12 calibration
- P9-13 inference adapter / SignalModel boundary
- P9-14 model registry metadata contract
- P9-15 prediction monitoring schema
- P9-16 phase validation gate
- P9-17 experiment record/reporting contract

Important: implementation-complete does not mean empirically successful.
Real-data results may still be inconclusive or reject the hypothesis.

The external test partition remains untouched by all Phase 9 model-selection
and calibration work. Phase 9 does not authorize live trading.

### Non-responsibilities

Prediction code must not:
- make BUY/SELL/TRADE decisions;
- size positions;
- create stops/targets;
- authorize risk;
- execute orders;
- bypass the Strategy or Risk Engine.

The output is probability information only.
