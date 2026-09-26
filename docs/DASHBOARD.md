# STOCK_BOT Operator Dashboard

The repository already exposes an observational dashboard payload through
`MonitoringRuntime.dashboard()`. This UI renders that payload without creating
a second telemetry or trading-control system.

## Use

Run an existing research/paper workflow, obtain its MonitoringRuntime dashboard
JSON payload, then open `dashboard/index.html` locally and select the JSON file.

The UI shows health, model telemetry, strategy rates, Risk utilization,
execution quality, performance metrics, alerts, and pipeline state.

**Live broker execution remains locked.** The dashboard cannot authorize trades,
change Risk/Strategy state, submit broker orders, or promote models.

No external frontend dependency is required.
