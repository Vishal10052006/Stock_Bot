# UPSTOX — Complete Integration Sequence Status

## Sequence

| Stage | Scope | Status |
|---|---|---|
| UPSTOX-01 | Provider adapter contract | COMPLETE |
| UPSTOX-02 | Sandbox authentication | COMPLETE — software boundary |
| UPSTOX-03 | Sandbox order lifecycle | COMPLETE — software boundary |
| UPSTOX-04 | Provider errors and rejections | COMPLETE — software boundary |
| UPSTOX-05 | Reconciliation | COMPLETE — software boundary |
| UPSTOX-06 | Operational certification | COMPLETE — software boundary |

## UPSTOX-08 readiness hardening

The provider adapter now validates Upstox position payload entries at the broker boundary. Non-object entries, malformed numeric fields, non-finite quantities/prices, and negative average prices are rejected before they can enter the canonical reconciliation contract.

Automated coverage is in `tests/execution/test_upstox_adapter.py`.

This hardening does not claim real sandbox position capability and does not weaken the BLOCKED-on-provider-unavailability rule.

## Real sandbox evidence — 2026-09-27

The opt-in official-SDK sandbox test was executed with real sandbox credentials and passed:

`SUBMIT → BROKER ORDER ID → CANCEL ORDER V3 ACK`

This verifies the provider-supported order submission/cancellation boundary. It does **not** verify history lookup or terminal-state reconciliation. The official SDK sandbox currently rejects `/v2/order/history`, so the full sequence below cannot be claimed from the observed sandbox runtime.

## Remaining external evidence

### 1. Real sandbox order transaction

The opt-in test requires a real sandbox token, instrument token and valid price. It must be executed outside normal CI with explicit confirmation. The repository must not contain the credential.

Expected full evidence:
`SUBMIT → BROKER ORDER ID → HISTORY LOOKUP → ELIGIBLE CANCEL → TERMINAL STATE`

Observed so far:
`SUBMIT → BROKER ORDER ID → CANCEL V3 ACK`

### 2. Sandbox position reconciliation

The production reconciliation contract is implemented and tested locally. The current Upstox sandbox documentation explicitly lists order APIs as sandbox-enabled; it does not establish the full position API as sandbox-enabled. Therefore no sandbox position evidence is claimed until the provider exposes and an actual response is observed.

## Safety

- Live execution remains disabled.
- Sandbox certification never authorizes live trading.
- Provider ambiguity never authorizes blind retry.
- Reconciliation mismatch or blocked state is not safe.
- Risk remains authoritative for quantity.

## Final engineering assessment

The Upstox integration sequence is **software-complete through UPSTOX-06**. The only remaining items are provider-observation evidence, not missing execution architecture.
