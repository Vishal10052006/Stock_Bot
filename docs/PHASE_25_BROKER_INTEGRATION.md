# Phase 25 — Broker Integration

## Implemented boundary

- Upstox V3 sandbox-first adapter;
- explicit injected broker client;
- deterministic provider instrument identity resolver;
- integer and lot-size validation;
- provider instrument token mapping;
- broker order-ID retention for lifecycle refresh/cancel;
- restart recovery through Upstox Order History tag lookup when the injected client supports it;
- fail-closed behavior when restart reconciliation is unavailable;
- canonical order status mapping;
- strict numeric and instrument tick-size validation;
- position snapshot mapping;
- explicit rejection of multi-child/sliced responses until the canonical execution contract supports aggregation.

The adapter remains disabled by default and refuses live configuration.

## Critical provider identity rule

A trading symbol such as ITC is not itself an Upstox V3 instrument token. The adapter therefore requires an explicit InstrumentResolver and sends the resolved provider token.

A production or sandbox run must use a verified current instrument master rather than a hand-written token list.

## Current provider reconciliation contract

Upstox documents Order History lookup by either order_id or tag. STOCK BOT uses the deterministic client_order_id as the Upstox order tag. After a process restart, the adapter can recover the latest order-history entry by tag and reconstruct the canonical broker order identity before refreshing it.

This is a software capability only; it does not constitute sandbox evidence.

## Operational prerequisites

Before any live consideration:

1. verify current Upstox API contract;
2. verify the current sandbox instrument master;
3. authenticate through the supported OAuth flow;
4. execute sandbox place -> query -> partial/full fill -> cancel lifecycle tests;
5. exercise restart recovery using Order History by tag;
6. verify broker positions against local state;
7. verify rate limits and error semantics;
8. complete current broker/exchange/regulatory checks.

No live order path is enabled by this phase.
