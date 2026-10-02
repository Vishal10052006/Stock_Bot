# STOCK_BOT Desktop Application

## D00 — Desktop Shell

Status: **FOUNDATION IMPLEMENTED**

### Boundary

D00 owns desktop navigation/composition state only.

It does not:
- generate trading decisions;
- authorize risk;
- submit broker orders;
- modify Strategy/Risk/Safety state;
- bypass the existing trading pipeline.

### Contract

`desktop.shell.DesktopShell` provides:
- immutable `DesktopView` metadata;
- deterministic view ordering;
- active-view selection;
- duplicate/unknown-view fail-closed behavior;
- JSON-safe state snapshot for future UI adapters;
- explicit `OBSERVATION_ONLY` authority marker.

### Next desktop stages

- D01 Market dashboard
- D02 Prediction panel
- D03 Explanation engine
- D04 Research/news panel
- D05 Screen observer panel
- D06 Decision timeline
- D07 Model telemetry
- D08 Risk panel
- D09 Paper account
- D10 Session replay

D00 intentionally uses no GUI framework yet. The shell contract is kept
framework-neutral so later UI work can consume existing runtime contracts
without duplicating trading logic.


## Module 5 D01-D10 implementation

All D01-D10 desktop boundaries are implemented as framework-neutral, read-only
read models and composition adapters in `desktop/read_models.py`, with the
application composition root in `desktop/application.py`.

| Stage | Implemented contract |
|---|---|
| D01 | `MarketDashboardState` + `build_market_dashboard` |
| D02 | `PredictionPanelState` + `build_prediction_panel` |
| D03 | `ExplanationItem` / `ExplanationState` + authoritative Module 7 `build_explanation` + audit |
| D04 | `ResearchEvidenceItem` / `ResearchPanelState` + causal filtering |
| D05 | `ScreenObserverPanelState` + reconciliation/validation visibility |
| D06 | `DecisionTimelineEvent` / `DecisionTimelineState` + stable timestamp ordering |
| D07 | `ModelTelemetryState` + monitoring dashboard adapter |
| D08 | `RiskPanelState` + safety/risk visibility |
| D09 | `PaperAccountState` + existing paper runtime adapter |
| D10 | `ReplayState` + deterministic step/pause/resume replay |

### Boundary guarantees

- Desktop is presentation/composition infrastructure only.
- Prediction remains probabilistic evidence; no prediction-to-order path exists.
- Research evidence is filtered by the existing `available_at <= decision_timestamp` boundary.
- Screen evidence remains contextual and observation-only.
- Risk remains owned by the Risk Engine.
- Paper account state is read from the existing paper runtime; no second account engine is created.
- Replay is immutable and explicitly rejects live-state mutation.
- Live broker execution is displayed as `LOCKED`; the desktop layer contains no broker submission path.

### Test coverage

`tests/desktop/test_module5_panels.py` covers the D01-D10 contracts,
including missing state, malformed probabilities, future research evidence,
screen fail-closed behavior, timeline ordering, telemetry absence, risk
absence, paper empty state, and replay isolation.
