# STOCK_BOT — M-11 Alert Orchestration

## Objective

M-11 centralizes alert policy after the M-10 persistent telemetry boundary. Evaluators still produce observational conditions; the orchestrator is responsible for severity policy, correlation identity, repeat counting, and dashboard summaries.

## Alert flow

`producer telemetry → evaluator → AlertOrchestrator → MonitoringEngine → AlertManager → optional Journal → dashboard`

The orchestrator does **not** call Risk, Safety, Strategy, or Execution and cannot authorize, block, size, or submit a trade.

## Severity policy

The central default mapping is:

| Code | Severity |
|---|---|
| ERROR_RATE_EXCEEDED | CRITICAL |
| STALE_RATE_EXCEEDED | CRITICAL |
| FEATURE_DRIFT_WARNING | WARNING |
| FEATURE_DRIFT_EXCEEDED | CRITICAL |
| PREDICTION_DRIFT_WARNING | WARNING |
| PREDICTION_DRIFT_EXCEEDED | CRITICAL |
| MODEL_LOG_LOSS_EXCEEDED | CRITICAL |
| MODEL_CALIBRATION_DRIFT | WARNING |
| DAILY_LOSS_LIMIT_REACHED | CRITICAL |
| MAX_OPEN_POSITIONS_REACHED | CRITICAL |
| MAX_GROSS_EXPOSURE_REACHED | CRITICAL |
| EXECUTION_REJECTION_RATE_HIGH | WARNING |

Unknown codes use the requested severity, subject to the configured minimum default severity.

## Correlation and escalation

Each condition receives a deterministic correlation identifier derived from its code, component, and stable metadata. Volatile orchestration fields are excluded.

Repeated observations of the same condition increment `occurrence_count`. Optional `AlertRule.escalation_after` can raise severity to a configured higher level.

This is **alert escalation**, not trading escalation. It does not change Risk limits, Safety state, model configuration, strategy parameters, or broker behavior.

## Policy integration

`MonitoringPolicy.max_execution_rejection_rate` is now passed directly into the execution evaluator instead of relying on a hard-coded evaluator threshold.

## Dashboard

The dashboard payload now includes `alert_summary` with total count, counts by severity, and counts by alert code.

## Evidence boundary

M-11 tests establish deterministic implementation behavior only. They do not establish profitability, predictive skill, live-trading readiness, or the correctness of thresholds for future market regimes. Those require chronological real/paper observations and separate evidence review.
