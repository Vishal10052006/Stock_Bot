# UPSTOX-14 — Sandbox Partial-Fill Evidence

## Scope

UPSTOX-14 adds a deterministic, non-network capture boundary for partial-fill observations.

It consumes already-observed provider responses and does not submit, modify, cancel, or authorize orders.

## Classification

- Missing fill-state observation → UNVERIFIED.
- Matching broker order identity + valid partial quantity + partial status → VERIFIED.
- Broker identity mismatch → FAILED.
- Invalid partial quantity → FAILED.
- A fully filled order does not count as partial-fill evidence.

## Safety

Live broker execution remains LOCKED. Provider evidence is observational only and cannot change Risk-approved quantity or execution authorization.

## Provider boundary

This module does not claim that Upstox sandbox currently produces a real partial-fill event. That claim requires an intentionally executed provider integration observation. Until then, the capability remains UNVERIFIED.
