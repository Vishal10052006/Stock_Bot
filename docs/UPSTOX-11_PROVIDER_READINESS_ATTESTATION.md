# UPSTOX-11 — Provider Readiness Attestation

## Scope

This document defines the evidence/provenance boundary between STOCK_BOT software certification and real Upstox provider certification.

A readiness attestation is observational evidence only. It does not authorize live execution.

## Capability matrix

| Capability | Software evidence | Real-provider evidence | Current state |
|---|---|---|---|
| Authentication | Error classification + sandbox transport | Sandbox authentication was empirically observed in UPSTOX-07 | VERIFIED (sandbox only) |
| Place Order V3 | Adapter mapping/tests | Real sandbox Place Order V3 reached provider | VERIFIED (sandbox) |
| Broker order ID | Canonical order mapping/tests | Real sandbox returned provider order identity | VERIFIED (sandbox) |
| Cancellation | Adapter mapping/tests | Real sandbox Cancel Order V3 acknowledgement observed on 2026-09-27 | VERIFIED (sandbox) |
| Order history / final broker state | UNKNOWN/reconciliation semantics | Official SDK sandbox rejects the `/v2/order/history` call; current sandbox capability page lists order APIs, not history | BLOCKED (sandbox capability) |
| Partial fills | Paper/adapter failure coverage | No real-provider partial-fill evidence recorded | UNVERIFIED |
| Broker rejection | Provider error classification/tests | Invalid-instrument provider rejection was observed in sandbox | PARTIAL |
| Position reconciliation | Production read-only positions client + deterministic evidence runner | No real position snapshot has been collected in this repository record | UNVERIFIED |
| Rate limiting | Classification + bounded backoff policy | No provider rate-limit observation recorded | UNVERIFIED |
| Timeout / network recovery | UNKNOWN + reconciliation-first software semantics | No provider timeout recovery evidence recorded | UNVERIFIED |
| Process restart recovery | Paper/broker-truth rehydration tests | No real-provider restart observation recorded | UNVERIFIED |

## Provenance rules

1. Unit or integration tests using mocks prove implementation behavior, not broker behavior.
2. Real-provider evidence must identify the provider environment and the operation actually observed.
3. Sandbox evidence must not be upgraded into production/live evidence.
4. Missing provider state is UNVERIFIED or BLOCKED, never an implicit pass.
5. The production reconciliation contract must not be weakened because a sandbox capability is unavailable.
6. Evidence is non-authorizing: a passing attestation cannot enable broker execution.

## Current Upstox boundary

The current Upstox documentation identifies the production Get Positions endpoint and the sandbox-enabled order APIs. The project therefore maintains a separate read-only production position transport seam while keeping live execution locked.

The repository's empirical evidence now verifies sandbox authentication, Place Order V3 reachability, broker order identity, invalid-instrument rejection, and Cancel Order V3 acknowledgement. On 2026-09-27 the real sandbox lifecycle test passed after removing the unsupported post-cancel history lookup. The official SDK sandbox still rejects `/v2/order/history`, so full order-history reconciliation is not certified. Sandbox position reconciliation is likewise not claimed.

## Gate semantics

A provider capability is considered VERIFIED only when the repository has evidence for the actual provider behavior being claimed.

The provider-readiness gate therefore remains blocked while any capability required for safe live operations is unverified.

## Safety

- Live broker execution remains locked.
- Risk remains the sizing and authorization authority.
- UNKNOWN provider state requires broker-state reconciliation before any retry.
- No readiness report creates, modifies, cancels, or authorizes an order.

## Current evidence boundary

The real sandbox test has now passed for the provider-supported transaction boundary: `SUBMIT → BROKER ORDER ID → CANCEL V3 ACK`. This is not equivalent to terminal-state/history certification.

The current Upstox sandbox documentation states that the sandbox currently supports Place, Modify, and Cancel order APIs; the provider also documents Order History and Get Trades for API users, but the official SDK sandbox runtime currently rejects the history endpoint. Therefore the project records the observed sandbox runtime behavior rather than assuming the broader API documentation implies sandbox availability.

## Next evidence collection

Only collect real-provider evidence with intentionally supplied credentials in an explicitly controlled environment. Record the observed operation and outcome; never commit credentials or include tokens in logs, reports, or test output.
