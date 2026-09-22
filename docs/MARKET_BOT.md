# Market Bot

Market Bot is the descriptive market-state layer of STOCK_BOT. It consumes causal market observations and existing PIT/data infrastructure and produces a versioned MarketContext.

## Boundary

Market Bot does not place or create orders, make BUY/SELL decisions, approve risk, size positions, set stops or targets, execute trades, replace Research Bot, replace Analysis Bot, or produce stock-level prediction probabilities.

## Existing infrastructure reused

- market.data.historical.point_in_time_universe
- market.data.context PIT market/sector context and alignment
- market.regime.detector Phase 6 deterministic regime baseline
- existing market indicators, features and data-quality infrastructure
- intelligence.analysis.contracts.AnalysisInput without modifying the frozen Analysis Bot

## MB roadmap

MB-01 universe and benchmark adapter
MB-02 trend
MB-03 range/trend structure
MB-04 volatility
MB-05 breadth
MB-06 sector intelligence
MB-07 sector rotation
MB-08 correlation/dependency
MB-09 liquidity
MB-10 market strength/weakness
MB-11 regime transitions
MB-12 state/context fusion
MB-13 orchestration
MB-14 provenance/persistence boundary
MB-15 observability
MB-16 validation
MB-17 evaluation
MB-18 future statistical/ML regime research
MB-19 Analysis/Prediction integration boundary
MB-20 Strategy/Risk boundary
MB-21 failure handling
MB-22 versioning
MB-23 production readiness

## Causality

All rolling baselines are trailing. Baselines used to classify the current observation are shifted by one observation. Constituent data is cut off at the final benchmark timestamp before Market Bot calculations.

Missing information remains unavailable or partial; it is never fabricated.

## Regime

Phase 6 detect_market_regime remains the deterministic V1 regime authority. Its regime_probability retains its existing rule-confidence meaning and is not treated as a calibrated probability.

## Integration

market.bot.integration.build_analysis_input adapts MarketContext into the existing frozen AnalysisInput contract. Analysis Bot remains unchanged. Prediction, Strategy, Risk and Execution remain downstream authorities.

## Storage and monitoring

Market Bot exposes injected storage and monitoring protocols rather than introducing a second database or dashboard architecture.

## ML regime research

K-Means, GMM, HMM and other statistical models remain research-only until a controlled experiment demonstrates robustness against the deterministic baseline using temporal validation.
