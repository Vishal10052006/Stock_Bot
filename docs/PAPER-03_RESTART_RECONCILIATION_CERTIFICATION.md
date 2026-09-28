# PAPER-03 — Restart + Reconciliation Certification

## Objective

Certify that the broker-neutral execution engine can recover execution state after a process restart from authoritative paper-broker state and reconcile signed positions without blindly resubmitting orders.

## Certified cases

1. Filled order rehydration preserves status, filled quantity and average fill price.
2. Partially-filled order rehydration preserves the partial state.
3. An UNKNOWN order whose broker accepted the order resolves to FILLED without a second submission.
4. Missing broker state leaves the order UNKNOWN and fail-closed.
5. Malformed broker quantity is rejected during rehydration.
6. Signed long and short position reconciliation detects both match and mismatch.
7. Restart rehydration reconstructs an order from broker truth.

## Safety invariant

UNKNOWN -> QUERY BROKER -> RECONCILE -> ACTUAL STATE

Never:

UNKNOWN -> BLIND RESUBMIT

## Scope

This certification uses only the deterministic paper adapter. It does not authorize or contact the live Upstox broker. Live execution remains locked.

## Definition of Done

- [x] Restart rehydration exercised.
- [x] Full-fill recovery exercised.
- [x] Partial-fill recovery exercised.
- [x] Successful UNKNOWN reconciliation exercised.
- [x] Missing broker state remains UNKNOWN.
- [x] Malformed broker state rejected.
- [x] Signed position reconciliation exercised.
- [x] Duplicate submission prohibited during UNKNOWN recovery.
- [ ] Live broker certification — separate future gate.
