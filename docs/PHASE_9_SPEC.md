# Phase 9 — Prediction Bot Research Specification (P9-00 through P9-17)

## Frozen research question
Does Logistic Regression trained on the frozen Phase 5 feature schema add predictive information for LONG_SUCCESS / SHORT_SUCCESS / NO_EDGE over the majority-class baseline, class-prior baseline, and frozen Phase 8 BaselineStrategy?

## Hypothesis
H1: the Logistic Regression model provides measurable out-of-sample predictive information beyond the required baselines on the frozen temporal validation protocol.

## Null / failure
H0: the model does not add predictive information beyond the baselines.
Reject the hypothesis when the model fails the predeclared evidence criteria, or when the result is not stable across the required temporal/regime/symbol/date analyses.

## Fixed for P9
- NSE equities, 5-minute candles, frozen trading specification.
- Frozen Phase 5 FeatureDataset v1 and Phase 7 decision labels.
- 70/15/15 chronological split.
- 60-minute purge at temporal boundaries.
- Train-only preprocessing.
- Chronological calibration holdout inside the training partition.
- No test-set model selection.

## Required comparisons
1. Majority-class predictor.
2. Class-prior probability predictor.
3. Frozen BaselineStrategy v1.0.
4. Logistic Regression v1.0.
5. Random Forest only as a predeclared nonlinear benchmark, not an automatic replacement.

## Required metrics
Accuracy, balanced accuracy, macro precision/recall/F1, per-class precision/recall/F1, log loss, multiclass Brier, ECE, confusion matrix, predicted-class distribution, probability distribution, and signal frequency.

## Required slicing
Report by regime, symbol group, and date. Report raw observations and effective-sample-size limitations caused by overlapping labels and clustering.

## Leakage controls
Future information may enter only through the Phase 7 target. No future price, label metadata, post-decision feature, future MarketContext, or future sector membership may enter X.

## Decision rule
The phase records evidence. It does not promise that the model will be accepted. A negative or inconclusive result is valid. No P&L claim is permitted without realistic costs and slippage.

## Ownership boundary
Prediction outputs probabilities only. Strategy decides, Risk controls, Execution executes, Monitoring observes, and Learning proposes validated improvements.
