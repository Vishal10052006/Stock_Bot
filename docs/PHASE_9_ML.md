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

## Remaining Phase 9 work

1. Run the complete repository test suite after the new changes.
2. Run a real historical dataset through the complete trainer.
3. Record reproducible validation metrics.
4. Compare Logistic Regression and Random Forest on the same temporal split.
5. Add model artifact/version persistence and the Phase 9 SignalModel v1.0
   prediction contract.
6. Keep the external test partition untouched until later validation phases.

Phase 9 does not authorize live trading.
