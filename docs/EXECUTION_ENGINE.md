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
- `UpstoxSandboxClient`: sandbox-only HTTP transport; it accepts only the
  dedicated `https://sandbox.upstox.com` host and never supports live endpoints.

## Required validation

Run:

```bash
pytest -q tests/execution tests/paper tests/risk
pytest -q
```

A clean repository-wide test run is required after any execution-engine change.

## Completion extension — execution recovery and exits

The execution boundary now includes the remaining production-safety pieces that can be implemented without enabling live broker trading:

13. **UNKNOWN recovery** — `recover_unknown()` re-queries authoritative broker state and updates the lifecycle only when the broker can resolve the order. A missing broker record remains `UNKNOWN`; the engine never blindly resubmits the uncertain order.
14. **Exit execution** — `from_exit_authorization()` creates an explicit `purpose="EXIT"` order, requires the authorization quantity to match the requested exit quantity, requires the authorization direction to oppose the current signed position, and prevents exits larger than the observed position.
15. **Execution lineage** — lifecycle events retain `decision_id` and `purpose`, while deterministic client order IDs include the execution purpose. This links decision → authorization → order lifecycle without introducing a second journal system.
16. **Failure-matrix tests** — coverage now includes late broker acknowledgements, unresolved UNKNOWN orders, exit-size limits, exit idempotency, and lifecycle lineage.

### Safety invariant

An UNKNOWN submission is **not** evidence that the broker did not receive the order. The only safe automatic action is to query broker truth. If the broker cannot resolve the order, execution remains blocked in `UNKNOWN` and requires external operational resolution; no automatic duplicate submission is performed.

### Live execution status

These changes do **not** enable Upstox/live trading. The existing live lock, independent safety gate, broker validation requirements, reconciliation gates, and readiness provenance remain authoritative.

## Production-side completion

Production validation controls now live in `execution/production.py`: adapter contract checks, partial-fill and rejection coverage, restart rehydration, signed position reconciliation, kill-switch tests, execution monitoring, paper soak execution, backtest cost-assumption parity, and a fail-closed production readiness gate.

`ExecutionEngine.rehydrate()` rebuilds order state from broker truth using client IDs recovered from durable journal storage. Missing broker state remains unresolved rather than being recreated by duplicate submission.

`.github/workflows/execution-engine.yml` runs the execution suite and full repository regression for execution-related changes.

The final readiness gate remains blocked until provider-specific integration evidence exists for authentication, submission, acknowledgement, partial fills, rejection, cancellation, lookup, position reconciliation, rate limiting, timeout recovery, and process restart recovery.

Live broker execution remains locked.

## Upstox provider-contract validation

The Upstox adapter implements provider request/response mapping behind an injected client boundary. The adapter remains disabled by default and does not construct HTTP clients or read credentials.

The current Upstox V3 order contract uses quantity, product, validity, price, tag, instrument_token, order_type, and transaction_type; successful placement returns provider order IDs. The adapter preserves the Stock_Bot deterministic client order ID as the Upstox tag.

Provider-specific mapping tests cover:
- request payload construction
- filled-order response mapping
- partial-fill mapping
- broker rejection mapping
- broker-order lookup
- cancellation using the provider order ID
- signed position mapping
- disabled/fail-closed behavior

The adapter intentionally depends on an externally supplied client with place_order, find_order_by_tag, cancel_order, and get_positions methods. This keeps authentication and transport outside the execution domain.

## UPSTOX-VALIDATION-02 — sandbox evidence harness

`execution/adapters/upstox_sandbox.py` provides a deliberately sandbox-only
transport client. It uses Upstox's dedicated sandbox host and supports the
order placement, order-history lookup, and cancellation calls needed by the
current adapter contract.

The client:
- rejects any base URL other than `https://sandbox.upstox.com`
- requires a caller-supplied sandbox token
- never logs or persists the token
- never constructs a live API URL
- normalizes order history into the adapter's provider-client shape
- raises `UpstoxSandboxError` on transport, HTTP, or malformed-response failures

The opt-in integration test is `tests/execution/test_upstox_sandbox_client.py`.
It is skipped unless all of the following are supplied locally:

```bash
UPSTOX_SANDBOX_ACCESS_TOKEN
UPSTOX_SANDBOX_INSTRUMENT_TOKEN
UPSTOX_SANDBOX_PRICE
UPSTOX_SANDBOX_CONFIRM=YES
```

The test places one sandbox LIMIT order, resolves it by tag, verifies broker-order
lineage, and attempts cancellation when the order is still cancellable.

Current Upstox documentation explicitly lists Place Order and Cancel Order as
sandbox-enabled APIs. Upstox's sandbox announcement also describes order
details/history as available for sandbox orders, while the current sandbox
capability list does not include portfolio/position APIs. Therefore position
reconciliation is **not** claimed as sandbox evidence by this test; it remains
a separate provider/readiness gate.

These tests provide a mechanism for real provider evidence, but **no sandbox
evidence is claimed until the opt-in test has actually been run with a valid
sandbox credential, instrument token, and reachable provider endpoint**.

A failed DNS/network preflight is an environment/infrastructure failure, not
evidence of successful or unsuccessful broker authentication.

**Live trading remains locked.**
