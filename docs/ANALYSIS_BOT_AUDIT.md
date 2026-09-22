# Analysis Bot — Production Audit

The Analysis Bot is considered structurally ready for freeze when its final
audit passes and the complete repository test suite remains green.

## Required boundaries

1. Decision timestamps are timezone-aware.
2. Context symbols are normalized.
3. Analysis/feature/data versions are present.
4. Provenance declares the information-available-at-decision-time boundary.
5. Quality metadata exposes feature completeness.
6. Fundamental and valuation contexts use their deterministic schemas.
7. Analytical candidates contain no BUY/SELL/order authority.
8. Analysis remains downstream-neutral: Strategy, Risk and Execution retain
   trading authority.
9. Missing information remains missing; no future observation is silently
   filled into the past.
10. Real historical fundamental validation is required before using the
    fundamental layer for empirical trading research.

## Freeze criterion

A code-only audit can pass the structural criteria. It cannot certify
profitability, future returns, or the quality of an externally acquired
fundamental dataset. Those require separate empirical validation with
point-in-time data.
