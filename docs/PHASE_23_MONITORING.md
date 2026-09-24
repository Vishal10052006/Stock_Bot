# STOCK_BOT — Phase 23 Monitoring Engine

Implementation status: M-1 through M-8 implemented on `feature/phase-23-monitoring`.
Execution mode: Observational only.
Live trading remains locked.

## M-1 through M-8

| Module | Responsibility | Primary telemetry |
|---|---|---|
| M-1 | System | heartbeats, component health, failures |
| M-2 | Market Data | freshness, missing/duplicate candles, latency, invalid OHLC, reconnects, clock drift |
| M-3 | Features | missing/Inf/stale rates and feature distribution drift |
| M-4 | Model | prediction drift, accuracy, F1, log loss, Brier/calibration telemetry |
| M-5 | Strategy | signals, NO_TRADE, trades, P&L, expectancy, win rate, drawdown |
| M-6 | Risk | daily loss, exposure, positions, entries, risk utilization, kill-switch state |
| M-7 | Execution | submissions, fills, rejections, partial fills, latency, slippage, reconciliation |
| M-8 | Outcome/Learning | completed outcomes, journal linkage, learning evidence, candidate proposals |

## Architecture

```text
System / Market / Features / Model / Strategy / Risk / Execution / Outcome
                                |
                                v
                       MonitoringEngine
                                |
              +-----------------+------------------+
              |                 |                  |
              v                 v                  v
           Metrics            Drift             Alerts
              |                 |                  |
              +-----------------+------------------+
                                |
                                v
                         Append-only JSONL
                                |
                                v
                       Dashboard-ready Report
```

## Safety boundary

Monitoring never:
- places orders;
- resizes positions;
- changes StrategyEngine rules;
- changes RiskEngine controls;
- retrains models;
- promotes models;
- enables live execution.

An alert is an observation. Emergency alerts identify conditions that must be handled by the independent safety/execution-control layer.

## Alert semantics

- INFO: normal telemetry.
- WARNING: degradation or drift requiring investigation.
- CRITICAL: material operating or trading-system degradation.
- EMERGENCY: a hard-control or reconciliation condition is observed.

`AlertManager` adds notification-level duplicate suppression while the underlying alert remains persisted.

## Drift

Numeric distribution drift uses deterministic PSI. Feature drift can be evaluated per feature, and prediction drift can be evaluated for model output distributions.

The monitoring engine reports drift; it does not use drift alone to promote, retire, or alter a model.

## Performance

Completed trade outcomes are aggregated only from journal outcome records. The performance layer reports trade count, wins/losses, net/gross P&L, fees/slippage, expectancy, win rate, profit factor, maximum drawdown, average holding time, and MAE/MFE.

These are measurements, not profitability guarantees.

## Integration

Existing STOCK_BOT records are observed without changing their authority boundaries:
- `ml.prediction.monitoring.PredictionTelemetry` → M-4;
- `journal.models.TradeDecisionRecord` → M-5;
- `journal.models.TradeJournalRecord` → M-8;
- `execution.safety.SafetyDecision` → safety telemetry;
- `execution.reconciliation.ReconciliationReport` → M-7.

Trade IDs are used as the preferred correlation identity for decision/outcome telemetry.

## Real-data evidence boundary

The implementation is code-complete as a monitoring engine and contract layer. Real operational evidence still requires actual paper/live-safe streams and measurements.

Unit tests cannot manufacture real feed latency, execution latency, slippage, paper drawdown, live prediction drift, calibration over real outcomes, or broker reconciliation behavior.

## Repository files

```text
monitoring/
├── __init__.py
├── adapters.py
├── alerting.py
├── drift.py
├── engine.py
├── health.py
├── metrics.py
├── models.py
├── performance.py
├── reporting.py
├── rules.py
├── store.py
└── README.md

tests/
└── test_monitoring_engine.py
```