# STOCK_BOT — Module 5 Desktop AI Interface Roadmap

## Scope

Module 5 connects the completed STOCK_BOT intelligence/trading layers to one desktop operator interface.

The desktop layer is a presentation/composition boundary. It must consume existing contracts and runtime state rather than duplicate Market, Prediction, Strategy, Risk, Execution, Monitoring, Screen Observer, or Learning logic.

## Authority Boundary

```
Desktop UI
   ↓
Existing runtime/contracts
   ↓
Market / Analysis / Prediction / Strategy / Risk / Safety / Execution
```

The desktop interface:

- observes and presents system state;
- requests only already-authorized application actions;
- does not create trading authority;
- does not bypass Strategy, Risk, Safety, or Execution;
- does not modify model/strategy parameters directly;
- keeps live broker execution locked by the existing safety gates.

---

# Working Sequence

| Stage | Module | Scope | Status |
|---|---|---|---|
| D00 | Desktop Shell | Navigation + composition boundary | COMPLETE |
| D01 | Market Dashboard | Market state and pipeline overview | COMPLETE |
| D02 | Prediction Panel | Prediction/probability display | COMPLETE |
| D03 | Explanation Engine | Decision/explanation presentation | COMPLETE |
| D04 | Research/News Panel | Research and event intelligence | COMPLETE |
| D05 | Screen Observer Panel | TradingView/screen intelligence | COMPLETE |
| D06 | Decision Timeline | Auditable chronological decision view | COMPLETE |
| D07 | Model Telemetry | Model quality/health/uncertainty | COMPLETE |
| D08 | Risk Panel | Risk state and controls visibility | COMPLETE |
| D09 | Paper Account | Virtual portfolio/account state | COMPLETE |
| D10 | Session Replay | Historical session reconstruction | COMPLETE |

---

# D00 — Desktop Shell

**Status: COMPLETE**

Implemented:

- `DesktopView`
- `DesktopShell`
- deterministic navigation
- active-view state
- duplicate/unknown view validation
- observation-only authority marker
- shell tests
- desktop documentation

**DoD**

- shell is framework-neutral;
- navigation state is deterministic;
- no trading authority exists in the shell;
- tests cover invalid navigation and metadata.

---

# D01 — Market Dashboard

## Goal

Create the primary desktop landing view showing the current system/market state using existing runtime contracts.

## Implementation

### D01.1 — Dashboard contract

Create a desktop-facing read model containing:

- timestamp;
- selected symbol;
- market session state;
- latest market/candle state;
- active timeframe;
- data freshness;
- pipeline health;
- monitoring readiness;
- paper/live execution state.

### D01.2 — Runtime adapter

Connect the dashboard to existing:

- Market Bot/runtime;
- MonitoringRuntime;
- TradingResearchRuntime;
- existing dashboard payloads.

Do not create a second monitoring/dashboard engine.

### D01.3 — Dashboard view

Add:

- market header;
- current price/candle summary;
- market data freshness;
- system health;
- pipeline state;
- safety/live-lock state;
- navigation to other desktop views.

### D01.4 — Tests

Cover:

- empty state;
- stale data;
- missing telemetry;
- deterministic rendering payload;
- live execution locked;
- no mutation of trading authority.

**DoD**

D01 can display a coherent current system snapshot without owning any trading decision.

---

# D02 — Prediction Panel

## Goal

Expose Prediction Bot output as probabilistic information.

## Implementation

### D02.1 — Prediction read model

Display:

- LONG_SUCCESS probability;
- SHORT_SUCCESS probability;
- NO_EDGE probability;
- model identifier/version;
- feature/context timestamp;
- prediction timestamp;
- prediction horizon;
- uncertainty/calibration metadata where available.

### D02.2 — Provenance

Every displayed prediction must remain traceable to its existing model/prediction contract.

### D02.3 — Safety boundary

Prediction display must not become:

```
Prediction → Order
```

It remains:

```
Prediction → Strategy → Risk → Safety → Execution
```

### D02.4 — Tests

Cover missing predictions, stale predictions, malformed probabilities, provenance, and read-only behavior.

**DoD**

Prediction information is visible and traceable without granting prediction authority.

---

# D03 — Explanation Engine

## Goal

Present why the current system reached its observed decision/state.

## Implementation

### D03.1 — Explanation contract

Build a structured explanation payload from existing evidence:

- market context;
- analysis context;
- prediction;
- strategy decision;
- risk decision;
- safety state;
- execution state;
- relevant research/screen evidence.

### D03.2 — Decision explanation

Support states such as:

- NO TRADE;
- LONG candidate;
- SHORT candidate;
- risk rejected;
- safety blocked;
- execution pending/rejected/filled.

### D03.3 — Evidence/provenance

Each explanation item should identify its source layer and timestamp where available.

### D03.4 — Tests

Verify:

- causal ordering;
- missing upstream evidence;
- risk rejection explanation;
- safety rejection explanation;
- no fabricated reason.

**DoD**

The UI explains observed system decisions using existing evidence without inventing causes.

---

# D04 — Research / News Panel

## Goal

Expose Research Bot and event intelligence in the desktop interface.

## Implementation

### D04.1 — Research read model

Display:

- research evidence;
- source metadata;
- publication/availability timestamp;
- relevance/context;
- event intelligence;
- neutral/insufficient evidence states.

### D04.2 — Causality

Respect the existing research availability boundary.

No future information may appear as if it were available at the decision timestamp.

### D04.3 — Integration

Reuse the existing Research/Analysis contracts.

Do not create a second research engine.

### D04.4 — Tests

Cover:

- future evidence rejection;
- missing source;
- stale evidence;
- timestamp ordering;
- provenance preservation.

**DoD**

Research/news is observable from the desktop while preserving the existing causal research boundary.

---

# D05 — Screen Observer Panel

## Goal

Expose Module 4 Screen Observer state inside the desktop application.

## Implementation

### D05.1 — Screen status

Display:

- capture status;
- target window;
- chart detection;
- OCR status;
- detected symbol;
- detected timeframe;
- indicators;
- candle visual evidence;
- screen confidence.

### D05.2 — Reconciliation

Display:

- MATCH;
- MISMATCH;
- STALE;
- INVALID;
- future-observation rejection.

### D05.3 — Authority

Screen evidence remains contextual.

```
Screen → Context
Market Feed → Market Authority
```

### D05.4 — Tests

Cover unavailable capture, invalid screen evidence, low confidence, stale observations, symbol/timeframe mismatch, and observation-only behavior.

**DoD**

Desktop can inspect Screen Observer evidence without allowing screen data to bypass market authority.

---

# D06 — Decision Timeline

## Goal

Create one chronological, auditable view of the system's decision lifecycle.

## Timeline

```
Market Observation
      ↓
Research / Analysis
      ↓
Prediction
      ↓
Strategy
      ↓
Risk
      ↓
Safety
      ↓
Execution
      ↓
Outcome
```

## Implementation

### D06.1 — Event contract

Normalize existing events into a desktop timeline read model.

### D06.2 — Ordering

Use event timestamps and preserve causal ordering.

### D06.3 — Event details

Allow inspection of:

- event type;
- timestamp;
- symbol;
- state;
- source;
- reason;
- identifiers;
- provenance.

### D06.4 — Tests

Cover out-of-order events, missing events, duplicate events, and timestamp integrity.

**DoD**

A complete paper decision can be inspected chronologically from observation to outcome.

---

# D07 — Model Telemetry

## Goal

Expose model health without turning telemetry into model-management authority.

## Implementation

Display existing telemetry such as:

- model version;
- prediction counts;
- probability distribution;
- calibration observations where applicable;
- model errors;
- drift;
- monitoring alerts;
- data quality.

### Boundary

Telemetry may identify evidence requiring investigation.

It must not automatically:

- retrain;
- promote;
- replace;
- modify a production model.

### Tests

Cover missing telemetry, stale metrics, model identity, and read-only behavior.

**DoD**

Model behavior is observable and traceable through existing Monitoring/Self-Learning boundaries.

---

# D08 — Risk Panel

## Goal

Make risk state visible to the operator.

## Implementation

Display:

- risk readiness;
- exposure;
- position state;
- limits;
- daily loss state;
- kill switch state;
- risk approval/rejection;
- rejection reason;
- safety state.

### Boundary

The desktop panel must not become a second Risk Engine.

Any consequential action must go through the existing authoritative risk/safety path.

### Tests

Cover:

- risk rejection;
- limit breach;
- kill switch;
- missing risk state;
- stale state;
- read-only display.

**DoD**

The operator can inspect why a candidate is or is not risk-authorized without bypassing Risk.

---

# D09 — Paper Account

## Goal

Expose the virtual trading account and paper execution state.

## Implementation

Display:

- virtual cash;
- positions;
- orders;
- fills;
- P&L;
- exposure;
- execution state;
- reconciliation state;
- session statistics.

Reuse the existing Paper/Execution/Position/Journal contracts.

### Safety

D09 must remain paper/simulation oriented while live broker execution is locked.

### Tests

Cover:

- partial fills;
- rejected orders;
- duplicate events;
- reconciliation mismatch;
- position accounting;
- session close state.

**DoD**

The desktop can inspect the virtual account without creating an independent account engine.

---

# D10 — Session Replay

## Goal

Replay an auditable historical/paper session through the desktop interface.

## Implementation

### D10.1 — Session source

Consume existing journal/monitoring/paper-session evidence.

### D10.2 — Replay timeline

Support:

- session selection;
- chronological playback;
- pause/resume;
- step forward;
- event inspection;
- final reconciliation.

### D10.3 — Determinism

Replay must not mutate live trading state.

### D10.4 — Tests

Cover:

- deterministic replay;
- missing events;
- timestamp ordering;
- session boundary;
- replay/live isolation.

**DoD**

A completed paper session can be reconstructed from stored evidence without contacting the broker or changing current trading state.

---

# Cross-Module Engineering Rules

Every D-stage follows:

```
Existing Contract
      ↓
Desktop Read Model / Adapter
      ↓
Desktop View
      ↓
Focused Tests
      ↓
Regression Tests
```

## Never duplicate

The desktop must not create competing versions of:

- Market Engine;
- Research Engine;
- Analysis Engine;
- Prediction Engine;
- Strategy Engine;
- Risk Engine;
- Safety Gate;
- Execution Engine;
- Monitoring Engine;
- Self-Learning Engine;
- Screen Observer.

## Required invariants

1. Strategy remains decision authority.
2. Risk remains risk authority.
3. Safety remains an independent gate.
4. Execution cannot increase approved risk.
5. Monitoring remains observational.
6. Screen Observer remains contextual.
7. Prediction remains probabilistic evidence.
8. Research remains causal and provenance-bound.
9. Desktop remains presentation/composition infrastructure.
10. Live broker execution remains locked until the existing production gates authorize it.

---

# Working Implementation Order

```
D00  COMPLETE
 ↓
D01  Market Dashboard
 ↓
D02  Prediction Panel
 ↓
D03  Explanation Engine
 ↓
D04  Research / News
 ↓
D05  Screen Observer
 ↓
D06  Decision Timeline
 ↓
D07  Model Telemetry
 ↓
D08  Risk Panel
 ↓
D09  Paper Account
 ↓
D10  Session Replay
```

For each stage:

```
Inspect existing contracts
        ↓
Implement smallest integration boundary
        ↓
Add focused tests
        ↓
Run regression
        ↓
Fix failures
        ↓
Commit
        ↓
Move to next D-stage
```

## Current implementation target

**D01 — Market Dashboard**
