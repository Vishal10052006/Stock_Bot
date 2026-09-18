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

from market.data.metrics import DataQualityMetrics
from market.data.validation import MarketEventValidator
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2


def main() -> int:
    """Connect, subscribe, wait for one LTPC event, then disconnect."""
    symbol = os.getenv("UPSTOX_SMOKE_SYMBOL", "ITC").strip().upper()
    if not symbol:
        print("UPSTOX_SMOKE_SYMBOL must not be empty", file=sys.stderr)
        return 2

    config = UpstoxFeedConfig.from_env()
    mapper = UpstoxInstrumentMapper.from_env()

    # Validate canonical events before they reach downstream consumers.
    validator = MarketEventValidator()

    # Collect live-feed data-quality and connectivity telemetry.
    metrics = DataQualityMetrics()

    feed = UpstoxMarketFeed(
        config,
        mapper,
        protobuf_module=MarketDataFeedV3_pb2,
        event_validator=validator,
        metrics=metrics,
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

            snapshot = metrics.snapshot()

            print("[SMOKE] data quality snapshot")
            print(f"  events_received={snapshot.events_received}")
            print(f"  events_accepted={snapshot.events_accepted}")
            print(f"  events_rejected={snapshot.events_rejected}")
            print(f"  stale_events={snapshot.stale_events}")
            print(f"  duplicate_events={snapshot.duplicate_events}")
            print(f"  latency_avg_ms={snapshot.latency_avg_ms}")
            print(f"  latency_p95_ms={snapshot.latency_p95_ms}")
            print(f"  clock_skew_events={snapshot.clock_skew_events}")
            print(f"  connection_failures={snapshot.connection_failures}")
            print(f"  reconnect_attempts={snapshot.reconnect_attempts}")
            print(f"  reconnect_successes={snapshot.reconnect_successes}")
            print(f"  reconnect_failures={snapshot.reconnect_failures}")
            print(f"  missing_data_gaps={snapshot.missing_data_gaps}")
            return 0

        print("[SMOKE] feed ended before a market event was received", file=sys.stderr)
        return 1
    finally:
        feed.disconnect()
        print(f"[SMOKE] connected_after_disconnect={feed.connected}")


if __name__ == "__main__":
    raise SystemExit(main())
