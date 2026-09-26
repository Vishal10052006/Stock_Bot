# STOCK_BOT Model & Pipeline Operations Center — Phase 0–20

This dashboard is a real observability surface aligned to the supplied OPS CENTER reference. It is read-only with respect to trading authority.

## UI
Overview, Agents, Pipeline Trace, Decision Inspector, Model Observability, System Health, Learning Loop and Event Log are the primary routes. The primary roster is Research → Analysis → Market → Prediction → Strategy → Risk → Execution. Monitoring, Learning and Model Registry appear as expanded diagnostics.

## Data
Real runtime state flows through runtime → MonitoringJournal/evidence → DashboardService → JSON API/SSE → UI. Empty state is explicit. Synthetic replay must never be displayed as live telemetry.

## Phases
0 audit/source mapping; 1 shell; 2 agent registry; 3 pipeline trace; 4 inspector; 5 telemetry stream; 6 decision inspector; 7 causality/contracts; 8 model observability; 9 learning loop; 10 health; 11 event log; 12 replay; 13 persistence/API; 14 frontend integration; 15 E2E; 16 failure/resilience; 17 security/access; 18 performance; 19 production deployment; 20 completion gate.

## Rules
LIVE broker execution remains locked. Dashboard cannot authorize, size, submit, cancel or reconcile broker orders. Monitoring remains observational. Model Registry remains immutable/non-authoritative. Learning remains non-authoritative. Causality/PIT evidence is displayed, not overridden.

## Shared journal
Set STOCK_BOT_MONITORING_JOURNAL to the same append-only MonitoringJournal path used by the application composition root, then run: python scripts/run_dashboard.py

## Completion
A phase is only complete when source → contract → backend → evidence/event → API/stream → UI → automated test is demonstrated. Rendering alone is not completion.
