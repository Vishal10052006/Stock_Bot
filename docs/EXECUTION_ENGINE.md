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


## Risk-approved exposure boundary

Execution consumes the immutable RiskDecision.approved_quantity and
RiskDecision.approved_notional. A caller may not replace these values with a
different quantity or notional. If optional values are supplied to the
authorization boundary, they must exactly match the Risk-approved values.

This creates a fail-closed boundary:

Risk -> Safety -> Execution

Risk owns sizing; Safety can only block; Execution cannot reconstruct, enlarge,
or silently resize the approved order.


## Broker response invariants

The Execution Engine fail-closes broker responses before recording them as
accepted execution state. It verifies:

- client order identity matches the submitted order;
- requested quantity matches the immutable OrderRequest;
- filled quantity is within the requested quantity;
- every returned fill belongs to the same client order;
- fill quantities and prices are positive;
- FILLED means the complete requested quantity was filled;
- PARTIALLY_FILLED means a strictly positive but incomplete quantity was filled.

The client order identifier is deterministic for the decision, symbol, direction,
and Risk version. Re-submitting the same immutable request is therefore
idempotent; an already-journaled client order is not submitted to the adapter a
second time.

A malformed broker response must never be treated as a valid fill.
