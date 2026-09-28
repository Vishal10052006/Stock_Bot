# Upstox Provider Readiness Closure — 2026-09-27

## Purpose

Record the current boundary between STOCK_BOT software readiness and provider-observed evidence.

## Verified provider evidence

The real official-SDK Upstox sandbox test passed on 2026-09-27.

Observed boundary:

`SUBMIT → BROKER ORDER ID → CANCEL ORDER V3 ACK`

This verifies:
- sandbox authentication;
- Place Order V3 reaching the provider;
- broker order identity returned by the provider;
- Cancel Order V3 reaching the provider and returning an acknowledgement.

The test is opt-in and never runs in normal CI.

## Provider capability limitation

The current official SDK sandbox runtime rejects the V2 Order History request with the sandbox capability error:

`This API is not available in sandbox mode.`

The current Upstox sandbox documentation lists Place Order, Place Order V3, Place Multi Order, Modify Order, Modify Order V3, Cancel Order, and Cancel Order V3 as sandbox-enabled APIs. Therefore STOCK_BOT does not infer sandbox history availability from the broader production API documentation.

Full order-state evidence remains:

`SUBMIT → BROKER ORDER ID → HISTORY LOOKUP → ELIGIBLE CANCEL → TERMINAL STATE`

and is not certified from the current sandbox runtime.

## Software controls already implemented

The repository already contains deterministic, non-authorizing controls for:

| Capability | Software control | Real provider evidence |
|---|---|---|
| Partial fill | Provider response classifier | UNVERIFIED |
| Rate limit | Classification + bounded backoff | UNVERIFIED |
| Timeout/network | UNKNOWN + reconciliation-first recovery | UNVERIFIED |
| Process restart | Broker-truth rehydration / duplicate-submission guard | UNVERIFIED |
| Position reconciliation | Read-only production transport + canonical reconciliation | UNVERIFIED |

A local deterministic test can prove software semantics. It cannot be promoted to provider evidence.

## Production position reconciliation

The repository has a dedicated read-only production transport and evidence runner. It:
- uses GET only;
- accepts the access token only at runtime;
- does not log the token;
- normalizes provider positions through the existing adapter contract;
- compares provider positions with local positions using canonical reconciliation;
- fails closed on mismatch or unavailable provider state.

A real production position snapshot is still required before claiming provider-level position reconciliation.

## Readiness rule

Provider readiness remains fail-closed while required capabilities are UNVERIFIED, BLOCKED, or FAILED.

The independent live lock remains enabled regardless of readiness status.

## Final status

**Software / paper execution: COMPLETE for the certified boundary.**

**Real sandbox order submission + cancellation boundary: VERIFIED.**

**Full provider readiness: NOT YET VERIFIED.**

**Live real-money execution: LOCKED.**
