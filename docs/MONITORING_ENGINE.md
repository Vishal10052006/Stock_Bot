# STOCK_BOT — Monitoring Engine

Monitoring is a cross-cutting observational subsystem. It observes system health, market/data telemetry, feature quality, model behavior and drift, strategy behavior, risk utilization, execution quality, alerts, and dashboard-ready state.

## Authority
Monitoring never predicts trades, authorizes trades, sizes positions, places orders, mutates model/strategy configuration, or overrides Risk/Safety. Risk remains the trading veto authority; Independent Safety remains the execution blocker.

## Domains
- System health: component state and latency.
- Data/market: freshness, quality, missing/duplicate events and provider telemetry.
- Features: completeness/validity emitted by the feature pipeline.
- Model: prediction count, labeled accuracy, log loss, calibration metrics and prediction-distribution drift.
- Strategy: decision/trade/no-trade rates, directional mix and realized net P&L telemetry.
- Risk: equity, daily P&L, position/exposure utilization and observed hard-limit breaches.
- Execution: fills, rejections, partial fills, latency and slippage.
- Alerts: INFO, WARNING, CRITICAL, EMERGENCY with deterministic fingerprints.
- Dashboard: JSON-safe snapshot for CLI/API/UI consumers.
- Learning: monitoring is an evidence source only; it never retrains or promotes a model.

## Drift
Prediction/feature drift can use PSI with bins derived only from the reference distribution. Current observations cannot redefine the reference bins.

## Formal Phase 23 roadmap
M23.1 foundation → M23.2 system/data → M23.3 model → M23.4 strategy/risk → M23.5 execution → M23.6 drift → M23.7 alerts → M23.8 dashboard → M23.9 integration → M23.10 validation.

## Evidence boundary
Synthetic tests establish implementation behavior only. Production monitoring conclusions require real chronological observations from the market/paper pipeline.
