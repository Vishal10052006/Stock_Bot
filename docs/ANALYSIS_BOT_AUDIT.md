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


## End-to-end authority audit

The final integration audit also verifies the canonical downstream chain:

FeatureDataset/Regime → AnalysisContext → PredictionContext → StrategyDecision → RiskDecision.

The checks must preserve these boundaries:
- Analysis emits analytical context/candidates only.
- Prediction performs inference using the existing Phase 9 feature schema.
- Strategy remains the authority for LONG/SHORT/NO_TRADE.
- Risk remains the authority for pre-trade approval/rejection.
- No upstream analytical or model output may directly create an order.
- Market and sector context namespaces remain distinct at the integration seam.


## Final integration audit

The Analysis boundary is considered structurally complete when the following
interfaces are verified together:

1. ResearchContext is not newer than the Analysis decision timestamp.
2. Fundamental available_at is not newer than the decision timestamp.
3. Valuation as_of is not newer than the decision timestamp.
4. Prediction preserves Analysis timestamp, symbol, feature version and analysis version.
5. Strategy preserves Analysis timestamp and symbol.
6. Risk evaluates the Strategy direction and preserves timestamp/symbol identity.
7. Analysis candidates contain no BUY/SELL/ORDER authority.
8. AnalysisContext owns its mapping inputs so later caller mutation cannot rewrite a completed analysis result.

These are integration/contract checks. They do not certify prediction accuracy,
strategy profitability, or future trading returns.
