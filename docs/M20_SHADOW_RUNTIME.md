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

## M20.4 — approved research/evidence runtime

The branch now composes the existing RBI/PIB RSS providers with the causal ResearchContextBuilder. Evidence is deduplicated by document ID, ordered deterministically, and filtered through the existing point-in-time availability boundary before symbol contexts are built. The research layer has no authority to mutate production Strategy/Risk/Model state or submit broker orders.

## M20.5 — shadow session evidence journal

Each shadow session can now use an append-only JSONL journal with a stable session correlation ID. Start, completed-candle, and stop events are recorded through the existing MonitoringEvent/MonitoringJournal contracts, allowing deterministic session replay without granting trading authority.

## M20.6 — runtime-integrated session journaling

The M20 runtime now optionally records its own lifecycle into the append-only shadow session journal. Set `STOCK_BOT_SHADOW_JOURNAL` to enable persistence; if unset, no journal file is created. The runtime records session start, each completed candle, and session stop, and exposes the journal evidence in its operational snapshot. The journal remains observational and cannot submit broker orders.

## M20.7 — deterministic session manifest

Each persisted shadow session now exposes a deterministic SHA-256 manifest fingerprint binding the session ID, SHADOW safety posture, configured symbols, timeframe, completed-candle count, and journal-event count. The manifest is evidence metadata only and rejects any live-order or non-SHADOW configuration.

## M20.8 — monitoring telemetry bridge

M20 now publishes real-time market-data quality snapshots into the existing MonitoringRuntime. The bridge records observational telemetry and exposes the existing dashboard; it cannot authorize, modify, or submit trades.

## M20.9 — persistent monitoring telemetry

When the optional shadow session journal is enabled, the existing MonitoringRuntime is now constructed with that same append-only journal. M20 market-data health, metrics, and alerts therefore become replayable session evidence without creating any trading authority.
