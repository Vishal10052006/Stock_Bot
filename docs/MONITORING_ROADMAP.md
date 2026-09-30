# STOCK_BOT — Monitoring Module Roadmap

M-1 Foundation / health / metrics — COMPLETE
M-2 Drift detection — COMPLETE
M-3 Alerts — COMPLETE
M-4 Model monitoring — COMPLETE
M-5 Risk monitoring — COMPLETE
M-6 Execution monitoring — COMPLETE
M-7 Strategy monitoring — COMPLETE
M-8 Unified pipeline / dashboard — COMPLETE
M-9 Producer telemetry adapters — COMPLETE
M-10 Persistent telemetry journal — COMPLETE
M-11 Alert orchestration — COMPLETE
M-12 Readiness evaluation — COMPLETE
M-13 Performance monitoring — COMPLETE
M-14 Regime monitoring — COMPLETE
M-15 Validation gate — COMPLETE
M-16 Runtime integration facade — COMPLETE
M-17 Stable monitoring contract — COMPLETE
M-18 Completion documentation — COMPLETE
M-19 Runtime telemetry bridge — COMPLETE

M-20 Empirical evidence identity / validation — IMPLEMENTED
M-21 Chronological run accounting — IMPLEMENTED
M-22 Cross-layer monitoring coverage — IMPLEMENTED
M-23 Failure / calibration evidence semantics — IMPLEMENTED
M-24 Final empirical monitoring completion gate — VALIDATING

M-20..M-24 are evidence/completion gates over the existing Monitoring Engine.
They do not add trading authority or replace the empirical paper run.

## M-19 runtime boundary

`monitoring/runtime.py` provides the concrete one-way runtime collection boundary
for Market, Data Quality, Analysis, Model, Strategy, Risk, Execution, Performance,
and Regime telemetry. It feeds the existing pipeline and central engine and exposes
readiness/report/dashboard state.

M-19 includes reusable producer-seam wiring for Market Bot, Analysis Bot, and
Prediction Inference. The authoritative Paper Decision Loop remains wired for
Strategy/Risk/Execution. `trading/runtime_pipeline.py` provides the application
composition root: one `TradingResearchRuntime` owns one shared
`MonitoringRuntime` and passes it through Market Bot -> Analysis -> Prediction
and the authoritative Paper Decision Loop. Monitoring remains observational and
never replaces Risk or Independent Safety.

## M-20..M-24 empirical completion

The final completion gate is implemented in:

- `monitoring/empirical_completion.py`
- `scripts/trading/validate_monitoring_completion.py`
- `tests/monitoring/test_empirical_completion.py`
- `docs/MONITORING_M20_M24_COMPLETION.md`

Run:

`pytest -q tests/monitoring/test_empirical_completion.py && PYTHONPATH="$PWD" python3 scripts/trading/validate_monitoring_completion.py`

Default artifact:

`data/paper/empirical_paper_report_v3.json`

M-24 becomes COMPLETE only after the real empirical artifact passes this gate.
The gate is deliberately not a profitability or live-readiness claim.
