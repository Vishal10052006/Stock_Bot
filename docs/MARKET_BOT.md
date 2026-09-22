# Market Bot — MB-00 to MB-23
Market Bot is the market-understanding layer. It describes context and has no BUY/SELL, sizing, risk approval, or execution authority.
| ID | Area | Status |
|---|---|---|
| MB-00 | Architecture/boundary freeze | COMPLETE |
| MB-01 | PIT universe + benchmark | COMPLETE |
| MB-02 | Trend | COMPLETE |
| MB-03 | Range/trend structure | COMPLETE |
| MB-04 | Volatility | COMPLETE |
| MB-05 | Breadth | COMPLETE |
| MB-06 | Sector intelligence | COMPLETE |
| MB-07 | Sector rotation | COMPLETE |
| MB-08 | Correlation/dependency | COMPLETE |
| MB-09 | Liquidity/flow | COMPLETE |
| MB-10 | Strength/weakness | COMPLETE |
| MB-11 | Regime transition | COMPLETE |
| MB-12 | State fusion | COMPLETE |
| MB-13 | Orchestration | COMPLETE |
| MB-14 | Persistence/provenance | COMPLETE |
| MB-15 | Monitoring/dashboard | COMPLETE |
| MB-16 | Validation/testing | COMPLETE |
| MB-17 | Evaluation | COMPLETE |
| MB-18 | Statistical/ML regime research | COMPLETE (research-only) |
| MB-19 | Prediction boundary | COMPLETE |
| MB-20 | Strategy/Risk boundary | COMPLETE |
| MB-21 | Failure handling | COMPLETE |
| MB-22 | Versioning | COMPLETE |
| MB-23 | Production-readiness gate | COMPLETE (evidence-driven) |
Causality: rolling calculations use current/past observations only; missing data stays unavailable; historical external context must use the existing PIT/as-of infrastructure. V1 regime_probability is bounded deterministic confidence, not calibrated probability.
