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
- a filled order provides a positive average fill price;
- fill fees are finite and non-negative;
- position average prices are finite and strictly positive.

The client order identifier is deterministic for the decision, symbol, direction,
and Risk version. Re-submitting the same immutable request is therefore
idempotent; an already-journaled client order is not submitted to the adapter a
second time.

A malformed broker response must never be treated as a valid fill. If a
submission response is malformed, the local order is journaled as UNKNOWN
before the validation error is surfaced, preventing a subsequent caller from
blindly submitting the same client order again. Cancellation transport
failures or malformed cancellation responses likewise transition the order
from CANCEL_PENDING to UNKNOWN because cancellation outcome is not known.


UNKNOWN orders are unresolved rather than accepted in execution
metrics, keeping `ExecutionResult.accepted` and aggregate accepted-order
counts semantically aligned.

## Position reconciliation boundary

Broker positions are authoritative for reconciliation. The comparison is
fail-closed: duplicate symbols or invalid position values invalidate the
reconciliation rather than being silently normalized.

A PARTIALLY_FILLED order may legitimately leave a smaller signed position than
the requested order quantity. That broker position must be reconciled against
the local position snapshot before downstream state is considered synchronized.

An UNKNOWN order state remains unresolved; it must not be treated as a
successful fill or as evidence that the expected position exists.

UNKNOWN recovery is explicitly fail-closed and idempotent. If the broker
temporarily returns no order state, the local order remains UNKNOWN. Repeating
the refresh does not create UNKNOWN -> UNKNOWN lifecycle events. A later
authoritative broker snapshot may recover the order to OPEN,
PARTIALLY_FILLED, FILLED, CANCELLED, or another valid lifecycle state without
resubmitting the order. Re-submitting an already-journaled UNKNOWN request
returns the unresolved state with `accepted=False`; reconciliation is the
recovery path rather than a duplicate broker submission.



## Transition lifecycle provenance

Risk decisions carry the transition classification and approved projected
quantity when Portfolio position context is available. The immutable
ExecutionAuthorization preserves that provenance.

Supported transitions are:

- OPEN — broker order creates the new directional position.
- INCREASE — broker order adds only the approved incremental quantity.
- REDUCE — broker order releases the approved reduction quantity.
- FLATTEN — broker order releases the full existing quantity.
- REVERSE — broker order quantity contains the full closing leg plus the
  Risk-approved opening leg; the order side is the new direction.

Risk remains responsible for deriving these quantities. Execution does not
recompute transition sizing from the original Portfolio intent.


## Authoritative broker-state validation

Every broker snapshot accepted by the execution journal is validated for:

- client-order identity and requested quantity;
- finite cumulative filled quantity;
- fill identity uniqueness;
- fill quantities/prices and cumulative fill total;
- consistency between lifecycle status and cumulative fills.

The same validation is applied during initial submission, refresh, and
cancellation responses. This prevents malformed or internally inconsistent
broker state from becoming local execution state.

Cancellation is not treated as proof that no further fill can occur. A broker
race may produce a later authoritative FILLED snapshot after cancellation;
the state machine permits that correction and portfolio reconciliation follows
the final broker position.


The standalone broker reconciliation contract also supports signed
quantities for long/short positions, normalizes symbols, rejects zero or
non-finite quantities and non-positive/non-finite average prices, and allows
only representation-level floating-point noise (1e-12) when comparing
quantity and price.

### Position-set invariants

Position reconciliation canonicalizes symbols using strip().upper() and
requires the local and broker snapshots to contain exactly the same symbol
set. A symbol present on only one side is a reconciliation failure.

Signed quantities are compared as signed values, so a long/short sign reversal
cannot be hidden by absolute-value comparison. Quantities and average prices
must be finite, positions must be non-zero, and average prices must be
strictly positive. Duplicate symbols are rejected on either side.

A very small floating-point tolerance (1e-12) is allowed for quantity and
average-price representation noise; material differences remain failures.
These rules also apply to duck-typed adapter/test objects, so validation does
not depend on the broker adapter constructing PositionSnapshot instances.


### Order reconciliation invariants

The reconcile_order() method now applies the same broker-snapshot validation
used by submission, refresh, and cancellation. A broker snapshot is not
considered reconciled merely because status and filled quantity match: its
identity, requested quantity, fills, cumulative fill accounting, and lifecycle
consistency must also be valid.

Average fill prices are compared with the same 1e-12 representation tolerance
used for position reconciliation. Missing local journal/request state is a
reconciliation failure rather than an implicit recovery.
