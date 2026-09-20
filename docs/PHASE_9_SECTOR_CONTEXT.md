# Phase 9 — Sector Context Foundation

Phase 9 sector context has two independent inputs:

1. historical sector-index candles;
2. point-in-time stock-to-sector mappings.

The index candle provider is responsible only for the first input. It must
not infer stock membership.

## Point-in-time requirement

The existing \`SectorMapping\` contract selects the sector index effective at
each observation timestamp. Therefore a real training dataset must use dated
membership snapshots rather than a current classification applied backward.

A mapping artifact should contain at least:

\`\`\`text
symbol,sector_index_symbol,effective_from,effective_to
RELIANCE,NIFTY_OIL_AND_GAS,2026-09-09,
\`\`\`

The example above is a schema example, not a production dataset row.

## Why the previous real-data run had NaNs

The multi-symbol builder supplied \`market_context\` to
\`build_phase9_dataset\`, but did not supply \`sector_context\` or
\`sector_mappings\`. The enrichment code therefore correctly left all sector
features as NaN.

This is a wiring/data-source issue, not a defect in the causal alignment
algorithm.

## Source boundary

NSE Indices publishes sectoral index pages with constituent downloads and
historical index data. The repository now centralizes provider identifiers and
provides a reusable multi-index context builder.

Historical membership must still be reconstructed from dated authoritative
snapshots before it is used for older observations. Do not fill historical
sector membership by guessing from current constituents.

## Current implementation

- \`market/data/context/sector_registry.py\`
  - canonical sector index identifiers
  - provider-symbol registry
- \`market/data/context/sector_context.py\`
  - fetches multiple index series
  - builds the same causal return/volatility context columns as market context
- \`market/data/context/enrichment.py\`
  - continues to perform point-in-time membership selection
- \`tests/test_sector_context.py\`
  - contract tests for the new infrastructure

The remaining dataset-specific step is to provide the authoritative
point-in-time mappings for the symbols/date snapshots used by
\`build_phase9_real_dataset.py\`.
