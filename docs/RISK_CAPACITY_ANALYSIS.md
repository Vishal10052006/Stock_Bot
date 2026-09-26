# Risk Capacity Counterfactual Analysis

## Purpose

Issue #61 asks whether the observed paper-run signal starvation is materially
related to the interaction between Risk-first sizing and the frozen 75% gross
exposure ceiling.

This tool does **not** modify the frozen Risk policy.

It replays the same causal dataset through the existing
`HistoricalBacktestEngine` under explicitly named counterfactual
`RiskConfig` scenarios.

## Scenarios

1. Frozen 75% gross exposure, hard rejection.
2. Hypothetical 85% gross exposure, hard rejection.
3. Hypothetical 100% gross exposure, hard rejection.
4. Frozen 75% gross exposure with explicit resize enabled.
5. Hypothetical 85% gross exposure with explicit resize enabled.

For each scenario it records:

- strategy signals;
- Risk rejections;
- gross-exposure rejections;
- paper fills;
- completed trades;
- net P&L;
- maximum drawdown;
- profit factor;
- expectancy;
- Risk rejection reason counts.

## Interpretation boundary

A scenario comparison can quantify the effect of a hypothetical Risk
configuration on the supplied chronological dataset. It does not establish
that a changed policy is appropriate, profitable, robust, or live-ready.

The frozen 75% policy remains the reference case until separate evidence and
governance explicitly validate any change.

## Input contract

The tool accepts the existing Phase 9 strategy-ready artifact in either CSV or
Parquet form. It requires the canonical decision-time columns consumed by
`HistoricalBacktestEngine`; it does not rebuild indicators, features, regime,
or strategy decisions.

The backtest starting equity defaults to 100,000 and can be made explicit with
`--starting-equity`.

## Usage

CSV:

```bash
python -m scripts.trading.analyze_risk_capacity \
  --input <strategy-ready.csv> \
  --output data/research/risk_capacity_counterfactual.json \
  --starting-equity 100000
```

Parquet:

```bash
python -m scripts.trading.analyze_risk_capacity \
  --input <strategy-ready.parquet> \
  --output data/research/risk_capacity_counterfactual.json \
  --starting-equity 100000
```
