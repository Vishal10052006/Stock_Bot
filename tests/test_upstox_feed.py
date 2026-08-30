"""
Unit tests for the Upstox Market Data Feed V3 adapter.

All network and protobuf dependencies are replaced with deterministic
test doubles. No real credentials or live WebSocket connection are used.
"""

from datetime import datetime, timezone

import pytest

from market.data.events import MarketEventType
from market.data.ingestion.providers.upstox.config import UpstoxFeedConfig
from market.data.ingestion.providers.upstox.feed import UpstoxMarketFeed
from market.data.ingestion.providers.upstox.instrument_mapper import (
    UpstoxInstrumentMapper,
)


UTC = timezone.utc


class FakeWebSocket:
    """Deterministic WebSocket test double."""

    def __init__(self):
        self.closed = False
        self.timeout = None
        self.sent = []
        self.messages = []

    def send(self, payload, opcode=None):
        """Record outbound WebSocket messages."""

        self.sent.append(
            {
                "payload": payload,
                "opcode": opcode,
            }
        )

    def recv(self):
        """Return queued messages or end the stream."""

        if not self.messages:
            return None

        return self.messages.pop(0)

    def close(self):
        """Mark the connection closed."""

        self.closed = True


class FakeWebSocketModule:
    """Minimal websocket-client compatible test module."""

    ABNF = type(
        "ABNF",
        (),
        {
            "OPCODE_BINARY": 2,
        },
    )

    def __init__(self, websocket):
        self.websocket = websocket
        self.created_uri = None
        self.created_timeout = None

    def create_connection(self, uri, timeout):
        """Capture connection parameters and return the fake socket."""

        self.created_uri = uri
        self.created_timeout = timeout
        return self.websocket


def make_config():
    """Create deterministic feed configuration."""

    return UpstoxFeedConfig(
        access_token="test-token",
        mode="ltpc",
        timeout_seconds=7.5,
    )


def make_mapper():
    """Create deterministic internal-to-Upstox instrument mappings."""

    return UpstoxInstrumentMapper(
        {
            "RELIANCE": "NSE_EQ|RELIANCE",
            "TCS": "NSE_EQ|TCS",
        }
    )


def make_feed(websocket_module):
    """Create an Upstox feed with injected WebSocket dependencies."""

    return UpstoxMarketFeed(
        make_config(),
        make_mapper(),
        websocket_module=websocket_module,
    )


def test_connect_authorizes_and_opens_websocket(monkeypatch):
    """Connect should authorize first and then create the WebSocket."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.get_authorized_websocket_uri",
        lambda access_token, timeout_seconds: (
            "wss://example.test/feed"
        ),
    )

    feed = make_feed(websocket_module)

    feed.connect()

    assert feed.connected is True
    assert websocket_module.created_uri == "wss://example.test/feed"
    assert websocket_module.created_timeout == 7.5


def test_subscribe_requires_connection():
    """Subscriptions must not be sent before connection."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    with pytest.raises(
        RuntimeError,
        match="must be connected",
    ):
        feed.subscribe(["RELIANCE"])


def test_subscribe_rejects_empty_symbols():
    """An empty subscription request must fail explicitly."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket

    with pytest.raises(
        ValueError,
        match="at least one non-empty symbol",
    ):
        feed.subscribe([" ", ""])


def test_subscribe_normalizes_and_maps_symbols():
    """Subscription symbols should be normalized and mapped."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket

    feed.subscribe(
        [
            " tcs ",
            "RELIANCE",
            "reliance",
        ]
    )

    assert len(websocket.sent) == 1

    message = websocket.sent[0]

    assert message["opcode"] == 2

    assert b"NSE_EQ|RELIANCE" in message["payload"]
    assert b"NSE_EQ|TCS" in message["payload"]

    assert feed._subscribed_symbols == {
        "RELIANCE",
        "TCS",
    }


def test_disconnect_closes_socket_and_clears_state():
    """Disconnect should release the socket and subscriptions."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket
    feed._subscribed_symbols.update(
        {
            "RELIANCE",
            "TCS",
        }
    )

    feed.disconnect()

    assert websocket.closed is True
    assert feed.connected is False
    assert feed._ws is None
    assert feed._subscribed_symbols == set()


def test_events_requires_connection():
    """Events cannot be consumed before connection."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    with pytest.raises(
        RuntimeError,
        match="must be connected",
    ):
        list(feed.events())


def test_events_requires_protobuf_module():
    """Events require the generated protobuf dependency."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket

    with pytest.raises(
        RuntimeError,
        match="protobuf module",
    ):
        list(feed.events())


def test_events_ignore_text_frames():
    """Unexpected text frames should not become market events."""

    websocket = FakeWebSocket()
    websocket.messages = [
        "unexpected-text-frame",
    ]

    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket
    feed._protobuf_module = object()

    events = list(feed.events())

    assert events == []


def test_events_stop_when_socket_returns_none():
    """A closed stream should terminate event iteration cleanly."""

    websocket = FakeWebSocket()
    websocket.messages = [None]

    websocket_module = FakeWebSocketModule(websocket)
    feed = make_feed(websocket_module)

    feed._ws = websocket
    feed._protobuf_module = object()

    events = list(feed.events())

    assert events == []


def test_context_manager_disconnects_after_exception(monkeypatch):
    """Context management must release the connection on failure."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.get_authorized_websocket_uri",
        lambda access_token, timeout_seconds: (
            "wss://example.test/feed"
        ),
    )

    feed = make_feed(websocket_module)

    with pytest.raises(RuntimeError, match="expected test failure"):
        with feed:
            assert feed.connected is True
            raise RuntimeError("expected test failure")

    assert websocket.closed is True
    assert feed.connected is False


def test_events_convert_protobuf_ltcp_to_market_event():
    """Binary protobuf LTPC data should become a canonical MarketEvent."""

    from market.data.ingestion.providers.upstox.generated import (
        MarketDataFeedV3_pb2,
    )

    response = MarketDataFeedV3_pb2.FeedResponse()
    response.type = MarketDataFeedV3_pb2.live_feed

    feed = response.feeds["NSE_EQ|RELIANCE"]
    feed.ltpc.ltp = 1425.30
    feed.ltpc.ltt = 1_756_537_500_000
    feed.ltpc.ltq = 125

    websocket = FakeWebSocket()
    websocket.messages = [
        response.SerializeToString(),
        None,
    ]

    websocket_module = FakeWebSocketModule(websocket)

    market_feed = make_feed(websocket_module)
    market_feed._ws = websocket
    market_feed._protobuf_module = MarketDataFeedV3_pb2
    market_feed._subscribed_symbols.add("RELIANCE")

    events = list(market_feed.events())

    assert len(events) == 1

    event = events[0]

    assert event.symbol == "RELIANCE"
    assert event.exchange == "NSE"
    assert event.event_type == MarketEventType.TRADE
    assert event.price == 1425.30
    assert event.volume == 125.0
    assert event.exchange_timestamp.tzinfo == UTC
    assert event.received_timestamp.tzinfo is not None
    assert event.event_id.startswith("NSE_EQ|RELIANCE:")
