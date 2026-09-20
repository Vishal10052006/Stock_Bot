# STOCK_BOT — Analysis Bot Implementation

## Scope

This branch implements the Analysis Bot coordination layer across AB-0 through
AB-22 without duplicating the existing Phase 4 indicator, Phase 5 feature,
Phase 6 regime, market-context, PIT sector, or Research Bot infrastructure.

## Architecture

ResearchContext -> AnalysisEngine -> AnalysisContext -> downstream Market/Prediction layers.

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
