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

## Remaining external evidence

### 1. Real sandbox order transaction

The opt-in test requires a real sandbox token, instrument token and valid price. It must be executed outside normal CI with explicit confirmation. The repository must not contain the credential.

Expected evidence:
`SUBMIT → BROKER ORDER ID → HISTORY LOOKUP → ELIGIBLE CANCEL → TERMINAL STATE`

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
