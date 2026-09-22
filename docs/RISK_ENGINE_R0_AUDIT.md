# Risk Engine R0 Audit

## Repository state observed at R0
- Default branch: main.
- Current branch for this work: risk-engine/r0-r20.
- Phase 9 documentation is present and records P9-00 through P9-17 engineering
  coverage as complete, while explicitly requiring final real-data/full-suite
  empirical validation before a release claim.
- Existing Strategy -> Candidate path exists.
- Existing Risk package had only a deterministic AB-27 gate and did not perform
  sizing, portfolio limits, liquidity controls, drawdown checks, or a kill switch.
- Existing execution authorization was broker-free and consumed RiskDecision.
- Existing backtesting engine reused Strategy -> Risk -> ExecutionAuthorization,
  but the risk component was only the simple gate.
- Existing cost and fill models are available.
- Existing tests include test_risk_gate.py and broad repository tests.

## R0 boundary freeze
Strategy produces the candidate. Risk consumes the candidate plus causal
portfolio/market state. Risk produces an immutable RiskDecision. Execution
consumes authorization derived from that decision. Risk never calls a broker,
generates predictions, or creates strategy signals.

## Reuse decision
No replacement of TradeCandidate or StrategyDecision was required.
The new Risk Engine extends the existing trading/risk package and strengthens
the existing execution authorization boundary.

## R0 exit condition
The remaining work is validation. R0 design is frozen; empirical policy
selection is deferred to backtesting/OOS/walk-forward evidence.
