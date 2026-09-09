"""Integration tests for the Upstox V3 protobuf -> MarketEvent path.

Reference:
    Upstox MarketDataFeedV3.proto and Phase 3.2 of the Stock Bot roadmap.
"""

from datetime import datetime, timezone

from market.data.events import MarketEventType
from market.data.ingestion.providers.upstox.decoder import decode_feed_message
from market.data.ingestion.providers.upstox.proto_adapter import extract_ltpc
from market.data.ingestion.providers.upstox.generated import MarketDataFeedV3_pb2


def test_serialized_feed_response_decodes_to_ltp_and_market_event():
    """Serialize a real generated FeedResponse and recover its LTPC data."""
    response = MarketDataFeedV3_pb2.FeedResponse()
    response.type = MarketDataFeedV3_pb2.live_feed

    feed = response.feeds["NSE_EQ|RELIANCE"]
    feed.ltpc.ltp = 1425.30
    feed.ltpc.ltt = 1_756_537_500_000
    feed.ltpc.ltq = 125
    feed.ltpc.cp = 1410.00

    payload = response.SerializeToString()
    decoded = decode_feed_message(payload, MarketDataFeedV3_pb2)
    records = extract_ltpc(decoded)

    assert len(records) == 1
    record = records[0]
    assert record.instrument_key == "NSE_EQ|RELIANCE"
    assert record.price == 1425.30
    assert record.quantity == 125.0
    assert record.timestamp_ms == 1_756_537_500_000

    event = {
        "event_id": f"{record.instrument_key}:{record.timestamp_ms}:{int(record.quantity)}",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "event_type": MarketEventType.TRADE,
        "price": record.price,
        "volume": record.quantity,
        "exchange_timestamp": datetime.fromtimestamp(
            record.timestamp_ms / 1000.0, tz=timezone.utc
        ),
        "received_timestamp": datetime.now(timezone.utc),
        "sequence_number": record.sequence_number,
    }

    assert event["price"] > 0
    assert event["volume"] >= 0
    assert event["exchange_timestamp"].tzinfo == timezone.utc
