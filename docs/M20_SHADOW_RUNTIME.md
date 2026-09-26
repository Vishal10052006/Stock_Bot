# M20.1 + M20.2 — Bootable SHADOW Runtime

## Scope

M20 connects STOCK_BOT to the real Upstox Market Data Feed V3 while keeping
live broker-order submission disabled.

Runtime boundary:

    Upstox WebSocket
        -> provider adapter
        -> MarketEvent
        -> validation
        -> data-quality metrics
        -> CandleAggregator
        -> completed Candle

M20 does not authorize, submit, modify, or cancel broker orders.

## Safety contract

The runtime starts only in SHADOW mode. The supported settings are:

    STOCK_BOT_MODE=SHADOW
    STOCK_BOT_LIVE_ORDER_SUBMISSION=false

A truthy live-order setting is rejected. A non-SHADOW mode is rejected.
There is no M20 runtime code path that constructs or calls a broker execution
adapter.

## Required environment

- UPSTOX_ACCESS_TOKEN
- UPSTOX_INSTRUMENT_MAP

The token must remain local and must not be committed.

## First real-market smoke test

From the repository root:

    set -a
    source .env
    set +a

    python -m pytest -q tests/test_m20_shadow_runtime.py
    python scripts/smoke_test_upstox_feed.py
    python main.py --max-candles 1

For the first session, use one or two configured NSE equities and ltpc mode.
The runtime should print:

- mode: SHADOW
- live broker order submission: False
- Upstox connection/subscription success
- accepted live events
- a completed five-minute candle while the market is producing events
- data-quality evidence
- no broker order activity

If the market is closed, a completed five-minute candle may not be produced;
the lower-level feed smoke test can still verify connection and decoded event
delivery when the provider supplies data.

## Shutdown

Use Ctrl-C. The runtime disconnects the market-data socket in finally and does
not invoke any order API.

## Provider reference

Upstox documents Market Data Feed V3 as a WebSocket feed using Protobuf. The
subscription request uses instrumentKeys and a mode such as ltpc or full, and
the request is sent as a binary message.

## Exit criteria

M20.1 is complete when the runtime boots fail-closed in SHADOW mode and the
runtime safety tests pass.

M20.2 is complete when a real Upstox market-data session demonstrates:

1. authenticated WebSocket connection;
2. successful instrument subscription;
3. canonical MarketEvent generation;
4. event validation and data-quality metrics;
5. candle aggregation;
6. graceful disconnect/restart;
7. zero live broker-order submission.

M20 completion is evidence of a working real-market data path, not
authorization for live trading.


## M20.3 — causal shadow candle buffer

Completed canonical candles are retained in a bounded in-memory buffer per symbol. The buffer enforces chronological ordering, rejects duplicate timestamps, keeps symbols independent, and exposes an OHLCV DataFrame for later causal feature/context stages. It does not generate signals, authorize trades, or call a broker.

## M20.3 — shadow decision trace

The M20 branch now exposes a trace boundary around the existing authoritative PaperDecisionLoop. Each processed decision records strategy direction/reason, Risk status/reason, ExecutionAuthorization status/reason, and any paper-order status. This is observational/paper-only and does not add broker submission authority.
