# Execution Engine — CERT-01 to CERT-12 Certification Matrix

**Scope:** software/paper/provider-readiness evidence only.  
**Safety boundary:** this artifact never authorizes live trading.

The matrix is fail-closed. Missing evidence is not PASS, and provider evidence is never inferred from unit tests.

| ID | Certification | Gate field | Evidence boundary |
|---|---|---|---|
| CERT-01 | Broker contract | `broker_contract_validated` | Adapter contract + response validation |
| CERT-02 | Failure matrix | `failure_matrix_validated` | Timeout/network ambiguity/rejection |
| CERT-03 | Idempotency | `idempotency_validated` | Duplicate replay / one broker identity |
| CERT-04 | Restart recovery | `restart_recovery_validated` | Rehydration from broker truth |
| CERT-05 | Position reconciliation | `reconciliation_validated` | Signed local vs broker positions |
| CERT-06 | Kill switch | `kill_switch_validated` | Independent safety block |
| CERT-07 | Monitoring | `monitoring_validated` | Execution metrics and latency |
| CERT-08 | Paper soak | `paper_soak_validated` | Paper execution + unknown/reconciliation safety |
| CERT-09 | Backtest/execution parity | `backtest_execution_parity_validated` | Slippage/fee assumption parity |
| CERT-10 | Operational runbook | `operational_runbook_validated` | Preflight/incident/shutdown procedures |
| CERT-11 | CI | `ci_validated` | Explicit repository regression/CI evidence |
| CERT-12 | Provider evidence | `provider_evidence_validated` | Externally observed broker behavior |

## Status semantics

- **PASS:** required evidence is explicitly present and the check succeeded.
- **PARTIAL:** implementation exists but the complete evidence requirement is not met.
- **BLOCKED:** a dependency or provider limitation prevents certification.
- **UNVERIFIED:** evidence has not been collected.
- **FAILED:** the required check produced a failure.

Only **PASS** satisfies the production-readiness mapping.

## Current known evidence

The repository already contains software-level implementations for the execution controls above, and the real Upstox sandbox Place Order V3 → Cancel Order V3 integration has been exercised externally.

That provider result is scoped only to the behavior actually exercised. It does not certify partial fills, rate limiting, timeout/network recovery, process restart, or production position reconciliation.

## Live lock

`ProductionReadinessGate` remains independent from the live execution safety lock. Even a complete readiness report does not authorize real-money trading. The independent safety gate must remain satisfied, and the provider evidence boundary must be explicitly certified.

## Implementation

- `execution/certification_matrix.py` — stable CERT-01..CERT-12 definitions, evidence records, fail-closed report, and gate-value mapping.
- `execution/production.py` — production readiness fields include the certification controls plus an independent live-lock validation field.
- `tests/execution/test_certification_matrix.py` — matrix invariants and fail-closed behavior.
