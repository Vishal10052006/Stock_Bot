# Phase 15 — Walk-Forward Validation

## Objective
Phase 15 tests whether the frozen trading/research configuration remains stable across sequential changing market periods.

## Contract
- deterministic chronological expanding TRAIN → PURGE → TEST windows;
- non-overlapping future test blocks;
- configurable purge interval;
- required symbol-aware decision rows;
- duplicate symbol/timestamp rejection;
- training data cannot reach a test period;
- test partition mutation detection;
- fold-level accounting and deterministic artifact fingerprint;
- descriptive aggregate evidence when fold results expose BacktestMetrics.

## Evidence
The report can describe fold count, positive-fold fraction, total trades, total net P&L, average expectancy, worst observed drawdown, and train/test/purge row counts.

These are descriptive observations. No automatic profitability threshold or promotion decision is introduced.

## Required upstream controls
1. validated historical data;
2. causal feature construction;
3. Phase 13 leakage audit;
4. Phase 14 unseen OOS validation;
5. frozen strategy/model configuration.

If walk-forward validation exposes instability or leakage, return to the affected upstream phase and revalidate.

## Deliverable
Walk-forward report with deterministic provenance/fingerprint and regression coverage.

Live trading remains locked.
