# UPSTOX-06 — Operational Certification

## Final software gate

UPSTOX-06 consolidates the Upstox software controls into one fail-closed certification record:

1. adapter contract validated;
2. sandbox authentication boundary validated;
3. sandbox order lifecycle validated;
4. provider error/rejection handling validated;
5. reconciliation boundary validated;
6. CI validation recorded;
7. live execution remains locked.

Implementation:
- execution/upstox_operational_certification.py
- tests/execution/test_upstox_operational_certification.py

## Important boundary

This is an operational **software** certification gate. It is not a live-trading authorization gate.

Upstox currently documents sandbox support for order placement, modification and cancellation. The public sandbox documentation does not establish the full position-reconciliation surface used by this project's production reconciliation contract. Therefore the project records provider position evidence separately rather than assuming it.

## Final status

**UPSTOX-04 software certification: COMPLETE**

**UPSTOX-05 software certification: COMPLETE**

**UPSTOX-06 software certification: COMPLETE**

**Real sandbox transaction evidence: PENDING**

**Real sandbox position-reconciliation evidence: PENDING provider capability/evidence**

**Live execution: LOCKED**
