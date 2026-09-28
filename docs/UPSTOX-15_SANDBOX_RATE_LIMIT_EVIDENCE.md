# UPSTOX-15 — Sandbox Rate-Limit Evidence

## Scope

UPSTOX-15 adds a deterministic evidence boundary for an already-observed Upstox
rate-limit response and a bounded backoff policy primitive.

## Evidence semantics

- HTTP 429 is the explicit provider signal used to verify rate limiting.
- Retry-After may be captured when present.
- Non-429 responses remain UNVERIFIED for rate-limit evidence.
- Malformed status/header values fail closed.
- Evidence capture performs no network I/O.
- The backoff helper is deterministic and capped; it does not perform retries.

## Safety

This milestone does not place, modify, cancel, or retry an order. It does not
authorize execution and does not change Risk authority. Live broker execution
remains locked.

## Limitation

A local deterministic test of an HTTP 429 response is not real-provider
sandbox evidence. The provider capability remains UNVERIFIED until an
intentional real Upstox observation is recorded.
