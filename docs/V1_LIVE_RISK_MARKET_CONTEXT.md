# V1 Live Risk Market Context

## Boundary

The Upstox risk-context provider is authoritative for broker/account state. It must not invent market-volatility values.

The canonical live decision already contains the causal indicator row used to construct the trading candidate. V1 now copies the observed ATR from that row into the live Risk context immediately before Risk evaluation.

## Rules

- Prefer `atr_14` when the canonical indicator schema provides it.
- Otherwise use the available causal `atr_*` indicator column.
- Missing ATR blocks the actionable manual-review path.
- Non-positive or non-numeric ATR blocks the actionable manual-review path.
- No synthetic ATR is permitted.
- Account state remains sourced from the read-only Upstox provider.

This separates two observation boundaries correctly: broker/account truth comes from the account observer; market-volatility truth comes from the canonical market-analysis row.

## Safety

No broker order operation is introduced. V1 remains human manual BUY/SELL decision support.
