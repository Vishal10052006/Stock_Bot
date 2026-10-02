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
| CERT-11 | PASS | GitHub Actions Execution Engine Production Validation run #123 completed successfully for commit 96c60a78952edd2b5cd19524c53a999aa80204e8. The job completed the certification-matrix validation, execution test suite, and full-repository regression steps successfully. |
| CERT-12 | PARTIAL | A real Upstox sandbox Place Order V3 -> Cancel Order V3 integration test has passed. This does not certify unsupported sandbox behavior or production broker readiness. |

## CERT-11 — CI evidence

Workflow:

.github/workflows/execution-engine.yml

Observed GitHub Actions run:

- Workflow: Execution Engine Production Validation
- Run number: 123
- Run ID: 36329958184
- Commit: 96c60a78952edd2b5cd19524c53a999aa80204e8
- Job: execution-validation
- Conclusion: success

Completed validation steps:

1. Certification matrix validation
2. Execution production validation
3. Full repository regression

The remote workflow completed successfully. This is the required remote CI evidence for CERT-11.

Local validation performed during the same certification work also completed successfully:

- Certification matrix: 8 passed
- Execution suite: 226 passed, 2 deselected
- Full repository: 1740 passed, 2 deselected, 7 warnings

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



## Operator implementation additions

The current development branch adds:

- observation-only Stock Scanner contract in `multi_stock/scanner.py`;
- atomic operator snapshot at `paper/virtual_sessions/<session-id>/operator_snapshot.json`;
- localhost-only read-only dashboard server in `scripts/serve_operator_dashboard.py`;
- Stock Scanner view in the desktop and Ops Center dashboards;
- multi-session CERT-08 campaign aggregation with optional cadence-gap validation;
- regression coverage for scanner, dashboard server, decision observation, and
  CERT-08 campaign behavior.

These additions do not change Strategy, Risk, Safety, broker authorization, or
live execution state.
