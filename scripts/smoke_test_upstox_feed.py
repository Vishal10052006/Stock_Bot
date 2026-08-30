"""Non-trading smoke test for the Upstox Market Data Feed V3 adapter.

This script verifies the live-data path only:
    Upstox WebSocket -> protobuf -> LTPC -> MarketEvent

No trading signals or orders are generated.

Reference:
    Phase 3.2 — Live Market Feed Adapter.
"""

from __future__ import annotations

import os
import sys
from time import monotonic

from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.instrument_mapper import UpstoxInstrumentMapper
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2


def main() -> int:
    """Connect, subscribe, receive one canonical event, then disconnect."""
    symbol = os.getenv("UPSTOX_SMOKE_SYMBOL", "RELIANCE").strip().upper()
    if not symbol:
        print("UPSTOX_SMOKE_SYMBOL must not be empty", file=sys.stderr)
        return 2

    config = UpstoxFeedConfig.from_env()
    mapper = UpstoxInstrumentMapper.from_env()
    feed = UpstoxMarketFeed(
        config,
        mapper,
        protobuf_module=MarketDataFeedV3_pb2,
    )

    started = monotonic()
    try:
        feed.connect()
        print(f"[SMOKE] connected={feed.connected}")

        feed.subscribe([symbol])
        print(f"[SMOKE] subscribed={symbol}")

        for event in feed.events():
            elapsed_ms = (monotonic() - started) * 1000.0
            feed_latency_ms = (
                event.received_timestamp - event.exchange_timestamp
            ).total_seconds() * 1000.0

            print("[SMOKE] market event received")
            print(f"  symbol={event.symbol}")
            print(f"  exchange={event.exchange}")
            print(f"  event_type={event.event_type.value}")
            print(f"  price={event.price}")
            print(f"  volume={event.volume}")
            print(f"  exchange_timestamp={event.exchange_timestamp.isoformat()}")
            print(f"  received_timestamp={event.received_timestamp.isoformat()}")
            print(f"  feed_latency_ms={feed_latency_ms:.3f}")
            print(f"  elapsed_ms={elapsed_ms:.3f}")
            return 0

        print("[SMOKE] feed ended before a market event was received", file=sys.stderr)
        return 1
    finally:
        feed.disconnect()
        print(f"[SMOKE] connected_after_disconnect={feed.connected}")


if __name__ == "__main__":
    raise SystemExit(main())
