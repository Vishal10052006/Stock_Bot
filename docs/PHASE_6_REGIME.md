# Phase 6 — Market Regime Detection

Phase 6 provides a deterministic, causal market-state layer over the Phase 5 market context.

## V1 regimes

- `TREND_UP`
- `TREND_DOWN`
- `RANGE`
- `HIGH_VOLATILITY`
- `LOW_VOLATILITY`

The project roadmap assigns rule-based detection to V1; K-Means, Gaussian Mixture, and Hidden Markov Model experiments belong to V2 and must only be retained if they improve robustness.

## Inputs

The detector consumes the frozen market-context columns already present in FeatureDataset v1:

- `market_return_3`
- `market_return_12`
- `market_volatility_20`

A FeatureDataset may contain many stocks at the same timestamp. The detector verifies that market context agrees across those rows before reducing it to one market observation per timestamp.

## Causal rules

1. Build a trailing median baseline from prior `market_volatility_20` observations only.
2. Compute the current volatility ratio against that prior baseline.
3. `HIGH_VOLATILITY` takes precedence at ratio `>= 1.50`.
4. `LOW_VOLATILITY` takes precedence at ratio `<= 0.75`.
5. Otherwise, classify `TREND_UP` when the 12-bar market return is `>= 0.25%` and the 3-bar return is `>= 0.05%`.
6. Classify `TREND_DOWN` symmetrically.
7. Remaining normal-volatility observations are `RANGE`.
8. During warm-up, the detector returns a missing regime rather than fabricating a state.

All thresholds are explicit configuration. They are not fitted on the complete historical dataset.

## `regime_probability`

In V1 this field is a bounded **rule-confidence score**, not a statistically calibrated probability. It is intentionally exposed under the roadmap-required `regime_probability` schema. Calibration/learned regime probabilities are a later research concern.

## Output

```text
timestamp
regime
regime_probability
```

## Leakage protection

The volatility baseline is shifted by one observation after its trailing median is calculated. Therefore the current volatility value cannot influence the baseline used to classify the current row. A dedicated test also perturbs future market data and verifies that earlier regime outputs remain unchanged.

## V2 boundary

Potential K-Means, Gaussian Mixture, or Hidden Markov Model implementations are deliberately not included in V1. Any learned regime detector must be evaluated with train/OOS or walk-forward discipline before replacing the deterministic baseline.
