# UPSTOX-04 — Provider Error & Rejection Certification

## Scope

UPSTOX-04 verifies that provider errors remain observable and fail closed.

Certified classes:
- authentication / authorization failure;
- request validation failure;
- explicit broker rejection;
- not-found response;
- rate limiting;
- provider unavailability;
- network/timeout ambiguity;
- unknown provider response.

## Safety rule

A timeout, network failure, provider outage, or unknown submission result is **not** permission to retry. It requires broker-state reconciliation first.

Explicit broker rejection must preserve a non-empty provider reason.

## Evidence

Automated certification is implemented in:
- execution/upstox_certification.py
- tests/execution/test_upstox_certification.py

Current Upstox documentation identifies HTTP 400, 401, 403, 404, 429, 500 and 503 classes and exposes explicit order rejection reasons/statuses.

## Status

**Software certification: COMPLETE.**

**Real-provider rejection evidence: PENDING.**

Live execution remains locked.
