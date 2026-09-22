# Market Bot Status

The Market Bot is implemented as a causal, descriptive market-state layer on top of existing STOCK_BOT market infrastructure.

## Current status

- MB-01 universe/benchmark boundary: implemented through existing PIT universe infrastructure.
- MB-02 trend: implemented.
- MB-03 range/trend structure: implemented.
- MB-04 volatility: implemented.
- MB-05 breadth: implemented.
- MB-06 sector intelligence: implemented for PIT-aligned membership input.
- MB-07 sector rotation: implemented.
- MB-08 correlation/dependency: implemented.
- MB-09 liquidity: implemented.
- MB-10 market strength/weakness: implemented with causal baselines.
- MB-11 regime transitions: implemented.
- MB-12 MarketContext fusion: implemented.
- MB-13 orchestrator: implemented.
- MB-14 provenance/persistence boundary: implemented without a second database.
- MB-15 monitoring: implemented.
- MB-16 validation/testing: implemented.
- MB-17 evaluation: implemented.
- MB-18 statistical/ML regime research: controlled walk-forward protocol implemented; no automatic promotion.
- MB-19 Analysis integration: read-only adapter to existing AnalysisInput.
- MB-20 Strategy/Risk integration: read-only context adapters.
- MB-21 failure handling: explicit unavailable/stale/insufficient-data failure types.
- MB-22 versioning: explicit schema/engine/regime versions.
- MB-23 production-readiness evidence: structured readiness report.

## Frozen boundaries

Research Bot and Analysis Bot remain unchanged.

Market Bot has no authority to:
- predict a stock outcome;
- choose a trade;
- size a position;
- approve risk;
- set stops or targets;
- create orders;
- execute trades.

## Important compatibility cleanup

The prototype-only Market Bot modules that duplicated the canonical engines were removed after the production implementation replaced them. The merged prototype test was rewritten to exercise the canonical implementation.

## Validation

The dedicated Market Bot suite and the full repository regression are run by .github/workflows/market-bot.yml.
