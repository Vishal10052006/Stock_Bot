# STOCK_BOT Execution Engine

## Scope

The production trading execution boundary is implemented in `execution/engine.py`.
The existing `execution/execution_engine.py` worker adapter is intentionally
preserved because it serves a different legacy worker-execution responsibility.

## EXEC-1 → EXEC-12

1. **Contracts** — immutable order, fill, snapshot, position, and result models.
2. **Validation** — execution requires an explicit `ExecutionAuthorization`.
3. **State machine** — lifecycle transitions are validated and journaled.
4. **Paper broker** — deterministic fills, fees, slippage, partial fills, and positions.
5. **Order management** — submit, refresh, cancel, open-order and journal access.
6. **Fill management** — immutable fill records and aggregate fill quantities.
7. **Position management** — broker position snapshots with signed long/short quantity.
8. **Idempotency/recovery** — deterministic client order IDs and fail-closed unknown states.
9. **Reconciliation** — local/broker order and position comparison.
10. **Execution metrics** — fill ratio, rejection rate, fees, quantities and lifecycle data.
11. **Execution journal** — immutable in-process order snapshots and lifecycle events.
12. **Validation tests** — unit/integration coverage for authorization, lifecycle,
    fills, shorts, reconciliation, cancellation, idempotency and metrics.

## Hard boundaries

```
Strategy → Risk → Safety → Execution → Broker Adapter
```

Execution does not calculate a larger position size than Risk approved.

Live broker execution remains locked. The Upstox adapter is deliberately
fail-closed until the broker integration is separately validated against the
current provider contract and the complete live-readiness gates pass.

## Current adapters

- `PaperBrokerAdapter`: deterministic, no network I/O.
- `UpstoxBrokerAdapter`: integration boundary only; live methods fail closed
  until an explicitly enabled, externally supplied client is validated.

## Required validation

Run:

```bash
pytest -q tests/execution tests/paper tests/risk
pytest -q
```

A clean repository-wide test run is required after any execution-engine change.

## Contract validation

The broker-neutral execution boundary is contract-tested independently of live
broker credentials. The paper adapter must satisfy the `BrokerAdapter`
protocol, preserve deterministic idempotency, and expose order/position state.
The Phase 25 locked gateway is separately tested to reject submit, order-state,
cancel, and position operations, including LIVE configuration.

These tests validate interface behavior only; they do not constitute current
Upstox API verification or live-readiness evidence.
