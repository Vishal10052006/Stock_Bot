# Execution Engine — E0–E17 Completion Record

This document maps the project execution roadmap in
`7. Execution_Engine_Tracker.pdf` to the implementation currently present in
`main`.

## Architecture boundary

```
Strategy / LiveSignal
        ↓
Risk Engine
        ↓
ExecutionAuthorization
        ↓
ExecutionEngine
        ↓
BrokerAdapter
   ┌────┴──────────────┐
PaperBroker        UpstoxAdapter
   │                    │
deterministic        disabled by
paper execution      default / sandbox-gated
```

Execution remains downstream of Risk and independent Safety. Execution never
creates trading decisions, enlarges Risk-approved quantity, widens stops,
overrides hard risk limits, or bypasses the kill switch.

## E0–E17 status

| ID | Roadmap stage | Implementation evidence | Status |
|---|---|---|---|
| E0 | Architecture Integration | Existing Strategy/Risk authorization boundary, paper runtime, backtest broker/fill/cost models, execution engine, safety and adapter layers are integrated without duplicating upstream decision/risk logic. | COMPLETE |
| E1 | Canonical Execution Contracts | `OrderRequest`, `Fill`, `OrderSnapshot`, `PositionSnapshot`, `ExecutionResult`, `ExecutionEvent`. | COMPLETE |
| E2 | ApprovedOrder Boundary | `ExecutionAuthorization` + `authorize_risk_decision()`; `ExecutionEngine.from_authorization()` preserves exact Risk-approved quantity. | COMPLETE |
| E3 | Pre-Execution Validator | Authorization status, exact quantity, symbol, side, finite positive quantity, order-type/price validation, and safety authorization checks. | COMPLETE |
| E4 | Order State Machine | Explicit lifecycle enum and transition validator, including terminal states and UNKNOWN. Repeated identical observations are idempotent. | COMPLETE |
| E5 | Broker Abstraction | Broker-neutral adapter contract with submit/get/cancel/positions operations. | COMPLETE |
| E6 | Paper Broker | Deterministic in-memory paper adapter with configurable slippage, fees, partial fills, cancellation, and signed positions. | COMPLETE |
| E7 | Fill Management | Immutable fills, fill quantities, average fill price, fees, slippage, partial-fill preservation and fill aggregation. | COMPLETE |
| E8 | Position Management | Signed long/short position snapshots and fill-driven paper position accounting. | COMPLETE |
| E9 | Idempotency | Deterministic client order identity and duplicate submission protection; replay returns the existing authoritative snapshot. | COMPLETE |
| E10 | Retry & Recovery | Timeout/network failures fail closed; bounded backoff policy exists; recovery never blindly resubmits an uncertain order. | COMPLETE |
| E11 | Unknown Order Handling | UNKNOWN state is explicit; broker lookup is required before resolution; unresolved broker state remains UNKNOWN. | COMPLETE |
| E12 | Reconciliation | Order refresh/rehydration plus signed local-vs-broker position reconciliation and mismatch blocking. | COMPLETE |
| E13 | Stop/Target/Time Exit Execution | Approved EXIT authorization is enforced against the observed signed position; causal stop/target/max-holding behavior remains implemented in the paper/backtest execution path, with explicit exit-order creation at the broker-neutral execution boundary. | COMPLETE |
| E14 | Execution Journal & Audit | Immutable order snapshots and lifecycle `ExecutionEvent` lineage retain decision ID and execution purpose; replay/UNKNOWN transitions are tested. | COMPLETE |
| E15 | Execution Monitoring | Execution metrics cover order count, fills, partial fills, rejections, UNKNOWN, requested/filled quantity and latency; production monitor exposes operational snapshots. | COMPLETE |
| E16 | Backtest Integration | Backtest uses the existing paper/broker simulator, FillModel and TransactionCostModel; execution/backtest assumptions have an explicit parity check. | COMPLETE |
| E17 | Upstox Adapter + Safety Gates | Upstox mapping is isolated behind an injected client; official SDK sandbox transport exists; adapter is disabled by default; independent safety/production readiness gates fail closed. | COMPLETE (software boundary) |

## Validation coverage

The execution test surface covers:

- authorization and exact Risk sizing
- state transitions
- full and partial fills
- cancellation
- duplicate replay
- UNKNOWN recovery
- restart rehydration
- signed position reconciliation
- kill-switch behavior
- execution metrics
- paper soak execution
- backtest/execution cost parity
- bounded retry policy
- operational runbook checks
- production readiness fail-closed behavior
- Upstox request/response mapping
- sandbox transport contract tests

## Provider/live boundary

E17 is **not** a claim of live-broker certification.

The Upstox adapter remains disabled by default. Real sandbox evidence is opt-in and
requires externally supplied sandbox credentials and provider availability.
Position reconciliation remains a separate provider-readiness gate where the
current sandbox capability surface is insufficient.

Live broker execution remains locked.

## CI checkpoint

The latest pre-fix repository-wide CI run on commit
`8fdbac6d16d8f6a343414274e5a485692970d0d5` reached:

- Market Bot tests: PASS
- Phase 9 contract validation: PASS
- Full regression: 1615 passed, 4 failed, 1 deselected

The four failures were execution hardening regressions:
1. malformed paper price was not asserted as fail-closed UNKNOWN by the test;
2. repeated missing-broker refresh attempted UNKNOWN → UNKNOWN.

The subsequent fixes on `main`:
- make repeated identical execution states idempotent;
- assert malformed paper-provider prices remain fail-closed as UNKNOWN.

A fresh CI run must be green before treating the E0–E17 implementation as regression-validated.

## Safety invariant

```
UNKNOWN ≠ NOT RECEIVED
```

After an ambiguous submission, the engine queries broker truth. If broker truth
cannot resolve the order, the engine remains UNKNOWN and does not automatically
submit a duplicate.

Live execution remains locked.
