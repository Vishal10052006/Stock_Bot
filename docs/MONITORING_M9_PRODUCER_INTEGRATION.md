# Monitoring Engine — M-9 Producer Integration

## Objective
Connect existing producer telemetry to the central monitoring boundary without creating a second source of truth and without giving Monitoring any trading authority.

## Integrated producer boundaries
- Market Bot -> monitoring.adapters.market_health
- Analysis Bot -> monitoring.adapters.analysis_health
- Market data quality -> monitoring.adapters.data_quality_snapshot
- Analysis feature quality -> monitoring.adapters.analysis_feature_snapshot

The adapters are intentionally read-only and protocol-shaped. They translate existing telemetry; they do not call Risk, Strategy, Execution, broker, model mutation, or safety authorization paths.

## M-9 system/data monitoring
SystemMonitoringSnapshot measures total events, failed events, stale events, duplicate events, invalid events, missing-data gaps, average latency, and p95 latency.

evaluate_system_monitoring() derives error/staleness rates and emits observational alerts when policy thresholds are exceeded.

## M-9 feature monitoring
FeatureMonitoringSnapshot measures feature count, invalid/missing counts and rates, reference/current feature distributions, and PSI drift.

Feature drift is reported as WARNING or CRITICAL according to the central monitoring policy.

## Pipeline integration
MonitoringPipeline now exposes evaluate_system(...), evaluate_features(...), evaluate_model(...), evaluate_risk(...), evaluate_execution(...), and evaluate_strategy(...).

All measurements flow into the same MonitoringEngine.

## Authority invariant
Monitoring remains observational:

Producer -> Monitoring -> Metrics / Alerts / Dashboard

It does not become Monitoring -> Risk / Strategy / Execution.

Risk and Safety remain the components that can veto or control execution.

## Validation
Unit coverage was added for system monitoring, feature drift, and all producer adapter mappings. A local full-suite run before this increment reported 1537 passed, 7 warnings. A fresh local full-suite run is still required after these commits because this environment does not execute the repository pytest suite.