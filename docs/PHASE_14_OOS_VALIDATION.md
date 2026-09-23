# Phase 14 — Out-of-Sample Validation

## Objective

Phase 14 packages the final unseen-test evidence after Phase 13 leakage controls.
The final test set remains untouched until the strategy/model configuration is frozen.

## Evidence required

- chronological train/validation/test boundaries;
- test-set prediction alignment;
- final OOS trading metrics;
- fold-level stability observations;
- regime-specific performance;
- cost/slippage sensitivity;
- deterministic artifact fingerprinting.

The report preserves return/P&L, expectancy, drawdown, profit factor and trade count
through the authoritative BacktestMetrics contract.

## Decision boundary

decision defaults to UNDECIDED. The implementation does not invent a profitability
threshold or automatically promote a strategy. A future approval criterion must be
explicit, frozen and separately validated.

## Required execution order

1. Freeze the strategy/model configuration.
2. Run the Phase 13 leakage audit on the exact historical dataset.
3. Execute backtesting.evaluate_oos with the final frozen configuration.
4. Run authoritative backtest accounting on the untouched OOS test period.
5. Supply fold, regime and cost-sensitivity evidence.
6. Persist the OOSValidationReport fingerprint with experiment provenance.
7. Do not use OOS results to retune the same test period.

## Evidence boundary

A structurally valid OOS report is not proof of future profitability. OOS is an
evaluation stage, not a live-trading authorization stage.