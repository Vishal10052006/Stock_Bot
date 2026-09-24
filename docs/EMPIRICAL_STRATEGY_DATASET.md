# EMP-03 — Strategy-Ready Dataset

## Purpose

EMP-03 converts historical 5-minute NSE OHLCV into the exact decision-time dataset required by the authoritative paper decision loop.

The builder does not create a second implementation of the project's indicators, features, or market regime. It composes the existing authorities:

1. `market.indicators.engine.IndicatorEngine`
2. `market.features.builder.build_features`
3. `market.regime.detector.detect_market_regime`

## Frozen output schema

The Parquet output contains exactly:

- `timestamp`
- `symbol`
- `close`
- `regime`
- `regime_probability`
- `vwap_distance_pct`
- `rvol_20`
- `higher_high`
- `higher_low`
- `lower_low`
- `lower_high`

No Phase 7 label, future return, model prediction, order, position, or P&L field is included.

## Causal construction

### Phase 4

The indicator engine is run independently for each symbol. This is important because EMA/RVOL calculations are single-series calculations.

The existing indicator implementations are retained as the source of truth.

### Phase 5

`build_features()` receives a point-in-time market context derived from the benchmark OHLCV using `build_context_returns()`.

Market context is aligned backward in time by the existing context-enrichment layer. No future benchmark observation is used.

### Phase 6

`detect_market_regime()` is applied to the resulting feature frame.

The existing Phase 6 contract is retained:

- one regime per timestamp;
- volatility baseline is trailing and shifted by one observation;
- early rows without a usable baseline remain unclassified;
- `regime_probability` is a bounded rule-confidence score, not a statistically calibrated probability.

Warm-up/unclassified rows are excluded from the strategy-ready output rather than fabricated.

## Benchmark requirement

The Phase 6 regime requires market context. EMP-03 therefore requires a NIFTY 50 benchmark series.

Two input modes are supported.

### Mode A — benchmark included in the same OHLCV file

```bash
PYTHONPATH="$PWD" python3 scripts/trading/build_strategy_dataset.py \
  --ohlcv-parquet data/research_archive/research_ohlcv_validation.parquet \
  --market-symbol "NIFTY 50" \
  --output data/paper/strategy_ready.parquet
```

The benchmark rows are used only for market context and are not emitted as stock strategy rows.

### Mode B — benchmark supplied separately

```bash
PYTHONPATH="$PWD" python3 scripts/trading/build_strategy_dataset.py \
  --ohlcv-parquet data/research_archive/stocks.parquet \
  --market-parquet data/research_archive/nifty50.parquet \
  --market-symbol "NIFTY 50" \
  --output data/paper/strategy_ready.parquet
```

If no benchmark can be resolved, the builder fails closed. It does not invent market context.

## Lineage

For every generated Parquet file the builder writes:

`<output>.parquet.manifest.json`

The manifest records:

- source OHLCV SHA-256;
- benchmark SHA-256;
- output SHA-256;
- resolved benchmark symbol;
- row count;
- symbol set;
- period;
- exact output columns;
- versions of the Phase 4/5/6 authorities;
- causal-alignment declarations.

The raw input is never rewritten.

## Empirical boundary

EMP-03 proves that a deterministic strategy-ready dataset can be generated from a supplied historical OHLCV source through the existing causal Phase 4→5→6 stack.

It does not prove:

- profitability;
- statistical robustness;
- OOS performance;
- paper-trading sufficiency;
- execution quality;
- live readiness.

Those require the downstream empirical evidence gates.

## Leakage test

`tests/scripts/test_build_strategy_dataset.py` includes a future-mutation test. It changes OHLCV only after a cutoff and verifies that all earlier strategy-ready decision rows remain unchanged.

This is a software causality test, not evidence of trading performance.