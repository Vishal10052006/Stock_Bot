# UPSTOX-03 — Sandbox Order Lifecycle Certification

## Scope

UPSTOX-03 establishes the complete broker-order lifecycle boundary against the
Upstox sandbox without enabling live execution.

Lifecycle:

`ExecutionEngine → UpstoxBrokerAdapter → Upstox SDK sandbox → broker order history`

## Certified software behavior

The repository covers:

1. sandbox-only client construction;
2. sandbox order submission;
3. broker order-id extraction;
4. order lookup by deterministic tag;
5. broker status normalization;
6. cancellation through the provider;
7. authoritative post-cancel order-history lookup;
8. cancellation-state validation;
9. fail-closed provider response validation;
10. explicit separation of sandbox position support from order lifecycle.

The lifecycle test does not assume every sandbox order becomes filled. It accepts
the broker's observed lifecycle and cancels only while the order is eligible.

## Automated coverage

Tests verify:

- sandbox host restriction;
- Bearer authentication;
- sandbox order placement;
- latest order-history resolution;
- cancellation followed by authoritative history;
- SDK sandbox configuration;
- provider-error normalization;
- no silent assumption of sandbox position support.

The real-provider test is opt-in and skipped without explicit sandbox variables.

Required variables:

- `UPSTOX_SANDBOX_ACCESS_TOKEN`
- `UPSTOX_SANDBOX_INSTRUMENT_TOKEN`
- `UPSTOX_SANDBOX_PRICE`
- `UPSTOX_SANDBOX_CONFIRM=YES`

No credential is stored in the repository.

## Certification boundary

**Software certification: COMPLETE.**

**Real provider evidence: PENDING one opt-in sandbox run.**

This distinction is intentional: CI cannot truthfully claim a real broker
transaction without executing one against the current Upstox sandbox.

## Safety

Live execution remains disabled. Sandbox validation does not authorize live
execution and does not change production safety gates.

## Provider-evidence exit path

A successful opt-in run should demonstrate:

`SUBMIT → BROKER ORDER ID → HISTORY LOOKUP → ELIGIBLE CANCEL → CANCELLED`

or another valid documented terminal broker state.

Next: **UPSTOX-04 — Provider Error & Rejection Certification**.
