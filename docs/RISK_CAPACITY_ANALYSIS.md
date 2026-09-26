# Risk Capacity Counterfactual Analysis

## Purpose

Issue #61 asks whether the observed paper-run signal starvation is materially
related to the interaction between Risk-first sizing and the frozen 75% gross
exposure ceiling.

This tool does **not** modify the frozen Risk policy.

It replays the same causal dataset through the existing
`HistoricalBacktestEngine` under explicitly named counterfactual
`RiskConfig` scenarios.

## Existing empirical evidence

The supplied Monitoring Engine completion record documents an already-validated
EMP-05/EMP-06 paper run using this local strategy-ready artifact:

```text
data/paper/strategy_ready_20260803_20260915.parquet
```

Documented evidence for that run:

- 22,850 strategy-ready rows;
- period 2026-08-03 07:05 through 2026-09-15 09:55 UTC;
- 10 symbols: AXISBANK, BHARTIARTL, HDFCBANK, ICICIBANK, INFY, ITC, LT,
  RELIANCE, SBIN, TCS;
- 144 Strategy signals;
- 1 order/fill;
- 22,849 Risk rejections;
- 136 gross-exposure rejections;
- 7 open-position rejections;
- evidence fingerprint
  `814c56625a64c91ce01d50b4b9f4660da0159b91cdcd7630e2207cbdf331876f`.

The same completion record states that all 136 gross-exposure rejection
candidates exceeded the 75% gross-exposure ceiling even with zero existing
exposure, and reports a median risk-first proposed value of ₹213,555.60
against the ₹75,000 frozen gross-exposure ceiling.

This is **existing descriptive evidence**, not the result of the new
counterfactual sweep. The five-scenario replay below is required to quantify
what would change under the hypothetical policies.

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
or strategy decisions. When an EMP-02 paper dataset manifest is supplied, the
replay fails closed unless the artifact SHA-256 exactly matches the frozen
manifest.

The backtest starting equity defaults to 100,000 and can be made explicit with
`--starting-equity`.

The repository intentionally does **not** commit the large empirical Parquet
artifact. The documented local artifact must therefore be supplied from the
validated research/paper environment before the counterfactual report is
generated.

## Usage

If the strategy-ready artifact is not already frozen under EMP-02, freeze the
existing local artifact:

```bash
python scripts/trading/freeze_paper_dataset.py \
  --input data/paper/strategy_ready_20260803_20260915.parquet \
  --dataset-version paper-2026-08-20260915-v1 \
  --output data/paper/paper_dataset_manifest.json
```

Then run the counterfactual replay:

```bash
python -m scripts.trading.analyze_risk_capacity \
  --input data/paper/strategy_ready_20260803_20260915.parquet \
  --output data/research/risk_capacity_counterfactual.json \
  --starting-equity 100000 \
  --manifest data/paper/paper_dataset_manifest.json
```

CSV input is also supported:

```bash
python -m scripts.trading.analyze_risk_capacity \
  --input <strategy-ready.csv> \
  --output data/research/risk_capacity_counterfactual.json \
  --starting-equity 100000 \
  --manifest data/paper/paper_dataset_manifest.json
```

## Provenance in the output

When `--manifest` is supplied, the JSON report records the exact frozen
dataset identity used for replay:

- manifest version;
- dataset version;
- artifact SHA-256;
- row count;
- symbols;
- period start/end.

The manifest is verified before replay. A missing dataset version or SHA-256,
or any byte-level artifact mismatch, fails closed. Without a manifest, the
report explicitly records that frozen provenance was not supplied.

This provenance identifies the input artifact; it does not convert the
counterfactual results into profitability, robustness, or live-readiness
evidence.
