# Phase 25 — Broker Integration

## Implemented boundary

- Upstox V3 sandbox-first adapter;
- explicit injected broker client;
- deterministic provider instrument identity resolver;
- integer and lot-size validation;
- provider instrument token mapping;
- broker order-ID retention for lifecycle refresh/cancel;
- fail-closed refresh when broker identity is unavailable;
- canonical order status mapping;
- position snapshot mapping.

The adapter remains disabled by default and refuses live configuration.

## Critical provider identity rule

A trading symbol such as ITC is not itself an Upstox V3 instrument token. The adapter therefore requires an explicit InstrumentResolver and sends the resolved provider token.

A production or sandbox run must use a verified current instrument master rather than a hand-written token list.

## Operational prerequisites

Before any live consideration:

1. verify current Upstox API contract;
2. verify the current sandbox instrument master;
3. authenticate through the supported OAuth flow;
4. execute sandbox place → query → partial/full fill → cancel lifecycle tests;
5. verify restart and reconciliation behavior;
6. verify broker positions against local state;
7. verify rate limits and error semantics;
8. complete current broker/exchange/regulatory checks.

No live order path is enabled by this phase.
