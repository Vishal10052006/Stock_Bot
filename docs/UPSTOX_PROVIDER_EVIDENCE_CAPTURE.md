# Upstox Provider Evidence Capture

This runbook defines how to collect CERT-12 evidence without inventing unsupported provider behavior or enabling live trading.

## Evidence model

Use:

`execution/provider_evidence.py`

A provider observation is valid only when all of these are explicitly recorded:

- capability
- environment
- operation
- state
- detail

Allowed states are `VERIFIED`, `UNVERIFIED`, `BLOCKED`, and `FAILED`.

## Already observed

The real sandbox integration test verifies:

`Place Order V3 -> Cancel Order V3`

This is provider evidence for that specific lifecycle only.

## Required evidence still open

The current controlled plan identifies:

| Capability | Environment | Operation | Current state |
|---|---|---|---|
| order_history | sandbox | order-state lookup | UNVERIFIED |
| partial_fill | sandbox | partial-fill behavior | UNVERIFIED |
| rate_limit | sandbox | rate-limit response | UNVERIFIED |
| timeout_recovery | sandbox | ambiguous request recovery | UNVERIFIED |
| process_restart | sandbox | restart and rehydration | UNVERIFIED |
| position_reconciliation | production | read-only positions observation | UNVERIFIED |

Do not convert these records to VERIFIED from unit tests alone.

## Safe execution boundary

Provider evidence collection must remain:

- opt-in;
- sandbox-first where the provider supports the behavior;
- read-only for production position observation;
- isolated from live execution authorization;
- credential-safe: credentials must never be committed or pasted into repository files or chat.

## CERT-12 completion rule

CERT-12 can become PASS only after the required provider capabilities are explicitly observed and recorded at the appropriate provider/environment boundary.

Until then, CERT-12 remains PARTIAL and the live execution lock remains independent.
