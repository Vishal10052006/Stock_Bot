# UPSTOX-16 — Timeout / Network Recovery Evidence

## Scope

UPSTOX-16 adds a deterministic evidence boundary for an already-observed
ambiguous provider failure.

## Recovery semantics

- Timeout/network outcomes are treated as ambiguous.
- Provider-unavailable 5xx outcomes also require reconciliation.
- Ambiguous outcomes require broker-state reconciliation before retry.
- Authentication/validation/rejection outcomes do not claim timeout recovery.
- The capture helper performs no network I/O.
- The capture helper never retries or submits an order.

## Evidence semantics

A local deterministic observation can verify the software safety property:
**ambiguous outcome → reconciliation required**.

It does **not** establish real Upstox sandbox timeout/network behavior.
Real-provider timeout recovery remains UNVERIFIED until intentional provider
evidence is recorded.

## Safety

No execution authorization is produced by this module. Live broker execution
remains locked.
