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
