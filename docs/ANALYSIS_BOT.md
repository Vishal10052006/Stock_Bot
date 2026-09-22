# STOCK_BOT — Analysis Bot Implementation

## Scope

This branch implements the Analysis Bot coordination layer across AB-0 through
AB-22 without duplicating the existing Phase 4 indicator, Phase 5 feature,
Phase 6 regime, market-context, PIT sector, or Research Bot infrastructure.

## Architecture

ResearchContext + Market/Technical/Structure/Sector/Relative/Fundamental/Valuation Context -> AnalysisEngine -> AnalysisContext -> downstream Market/Prediction layers.

The Analysis Bot interprets existing causal feature/context data. It does not
create broker orders or replace Strategy/Risk/Execution responsibilities.

## Phase mapping

- AB-0: repository audit and architecture freeze.
- AB-1: immutable AnalysisInput / AnalysisContext contracts.
- AB-2: deterministic technical interpretation.
- AB-3: price-structure interpretation.
- AB-4: volume interpretation.
- AB-5: volatility interpretation.
- AB-6: market/index context adapter.
- AB-7: PIT sector-context adapter.
- AB-8: relative performance interpretation.
- AB-9: ResearchContext adapter.
- AB-10: feature/context composition.
- AB-11: AnalysisEngine.
- AB-12: analytical candidates (never trade orders).
- AB-13: provenance and quality metadata.
- AB-14: storage protocol + in-memory reference backend; no second database.
- AB-15: per-run health metrics.
- AB-16: feature health summary.
- AB-17: contract/integration tests.
- AB-18: explicit failure taxonomy.
- AB-19: downstream-neutral quality evaluation.
- AB-20: data/feature/indicator/analysis/research version tuple.
- AB-21: explicit AnalysisContext boundary for Market/Prediction consumers.
- AB-22: dashboard-ready metrics/context payloads.

## Fundamental analysis implementation

The fundamental layer is implemented as a provider-neutral, point-in-time subsystem:

- FUND-01: immutable `FundamentalSnapshot` contract.
- FUND-02: `FundamentalProvider` protocol plus deterministic in-memory and normalized CSV providers.
- FUND-03: causal alignment using `available_at <= decision_timestamp`.
- FUND-04: deterministic fundamental analyzer for profitability, margins, growth, leverage, liquidity and cash flow.
- FUND-05: derived fundamental metrics with explicit missing-data preservation.
- FUND-06: separate `ValuationSnapshot` for P/E, P/B, EV/EBITDA and FCF yield.
- FUND-07: AnalysisContext integration without trade authority.
- FUND-08: provenance records the fundamental schema version.
- FUND-09/FUND-10: contract, causality and future-data boundary tests.
- FUND-14/FUND-15: documented provider-neutral schema and dashboard-safe fundamental payload.

Human-required work is limited to acquiring/normalizing trustworthy historical financial data with correct publication/availability timestamps. The Analysis Bot does not embed vendor credentials or network acquisition logic.

## Existing components intentionally reused

- `market/indicators/*`
- `market/features/*`
- `market/data/context/*`
- `market/regime/*`
- `research/contracts/*`
- `research/causal/*`
- `research/integration/context.py`
- `workers/technical_worker.py`
- `workers/research_worker.py`
- `workers/sentiment_worker.py`

## Safety / causal rules

1. Analysis consumes information available at the decision timestamp.
2. Future outcome labels are not an Analysis Bot input.
3. Missing context remains missing.
4. Analysis candidates are not trade signals.
5. Analysis cannot bypass Strategy, Risk, or Execution.
6. Existing PIT sector membership and backward timestamp alignment remain authoritative.


## Final integration status

The Analysis Bot boundary now includes explicit downstream audit coverage for:

- ResearchContext causal timestamp versus Analysis decision time.
- Fundamental available_at versus Analysis decision time.
- Valuation as_of versus Analysis decision time.
- Analysis → Prediction timestamp, symbol, feature-version and analysis-version propagation.
- Analysis → Strategy timestamp and symbol propagation.
- Strategy → Risk direction identity.
- AnalysisContext ownership of mapping inputs to prevent post-build caller mutation.

The structural audit is downstream-neutral: it verifies contracts and causality,
not model accuracy, profitability, or future returns.

## Freeze status

Analysis Bot implementation and downstream authority boundaries are structurally
complete on this branch. Further work belongs to real-data validation or the
next model in the system rather than additional Analysis features.
