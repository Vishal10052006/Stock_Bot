# UPSTOX-05 — Reconciliation Certification

## Scope

UPSTOX-05 binds Upstox execution to the canonical broker/local reconciliation contract.

The reconciliation result is one of:
- MATCH — local and broker signed positions agree;
- MISMATCH — any quantity or average-price discrepancy is observable;
- BLOCKED — either authoritative snapshot is unavailable.

No mismatch or blocked state is treated as safe for continued execution.

## Certified behavior

- long and short signed quantities are compared;
- missing symbols are treated as zero on the opposite side;
- duplicate symbols fail closed;
- quantity mismatches are detected;
- average-price mismatches are detected;
- missing snapshots produce BLOCKED rather than MATCH.

Automated certification: tests/execution/test_upstox_reconciliation.py

## Provider limitation

Upstox's public documentation exposes a production Get Positions API, while the current sandbox API list is focused on order placement, modification and cancellation. Therefore this repository does not claim sandbox position reconciliation evidence without an observed supported sandbox position endpoint.

## Status

**Software certification: COMPLETE.**

**Real-provider position reconciliation evidence: PENDING provider capability/evidence.**

Live execution remains locked.
