# Execution Certification Evidence Record

This document records evidence that has actually been observed for CERT-01 through CERT-12. It is an evidence record, not a live-trading authorization.

## Current status

| ID | Status | Evidence boundary |
|---|---|---|
| CERT-01 | PASS | Broker-neutral execution contracts and adapter validation are covered by the execution test suite. |
| CERT-02 | PASS | Failure-matrix behavior for timeout, network ambiguity, duplicate replay, and broker rejection is covered by execution tests. |
| CERT-03 | PASS | Duplicate replay/idempotency behavior is explicitly tested. |
| CERT-04 | PASS | Restart/recovery behavior is explicitly tested at the software boundary. |
| CERT-05 | PASS | Signed position evidence and reconciliation behavior are explicitly tested at the software boundary. |
| CERT-06 | PASS | Kill-switch behavior is explicitly tested and remains independent of readiness. |
| CERT-07 | PASS | Execution monitoring/metrics behavior is covered by execution tests. |
| CERT-08 | PARTIAL | Paper-soak validation exists in the software/test framework; a long-duration operational soak has not been claimed here. |
| CERT-09 | PASS | Backtest/execution cost-assumption parity is explicitly tested. |
| CERT-10 | PASS | Operational preflight, incident, shutdown, and UNKNOWN-order handling are documented and tested. |
| CERT-11 | UNVERIFIED | The repository contains an execution-engine GitHub Actions workflow, but a successful remote workflow run for the certification branch has not yet been recorded in this document. |
| CERT-12 | PARTIAL | A real Upstox sandbox Place Order V3 -> Cancel Order V3 integration test has passed. This does not certify unsupported sandbox behavior or production broker readiness. |

## CERT-11 — CI evidence boundary

The execution workflow is:

.github/workflows/execution-engine.yml

It runs:

1. pytest -q tests/execution
2. pytest -q

A local full-suite result observed during certification work was:

1740 passed, 2 deselected, 7 warnings

Local execution is not substituted for GitHub Actions evidence. CERT-11 remains UNVERIFIED until a remote workflow run is observed and recorded.

## CERT-12 — provider evidence boundary

The observed provider test uses:

tests/execution/test_upstox_sandbox_client.py

The real sandbox integration path verifies:

Place Order V3 -> Cancel Order V3

The integration test requires explicit sandbox credentials/configuration and an explicit UPSTOX_SANDBOX_CONFIRM=YES opt-in.

The observed pass does NOT establish:

- production/live broker authorization;
- production position reconciliation;
- sandbox partial-fill behavior;
- provider rate-limit behavior;
- timeout/network recovery at the provider boundary;
- process-restart recovery against the provider;
- any provider capability not exposed by the sandbox path.

Therefore provider evidence remains PARTIAL and the live execution lock remains independent.

## Fail-closed rule

Missing or non-PASS evidence must not be converted to PASS. Provider evidence must be explicitly observed. The certification matrix and production readiness gate remain fail-closed.

**Live execution remains LOCKED.**
