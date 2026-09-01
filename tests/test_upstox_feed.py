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

def test_reconnect_restores_connection_and_subscriptions(monkeypatch):
    """Reconnect should open a new socket and restore active subscriptions."""

    first_socket = FakeWebSocket()
    second_socket = FakeWebSocket()

    class ReconnectingWebSocketModule(FakeWebSocketModule):
        """Return a new socket for each connection attempt."""

        def __init__(self):
            super().__init__(first_socket)
            self.sockets = [first_socket, second_socket]
            self.connection_count = 1

        def create_connection(self, uri, timeout):
            """Return the next deterministic socket."""

            self.created_uri = uri
            self.created_timeout = timeout

            socket = self.sockets[self.connection_count]
            self.connection_count += 1

            return socket

    websocket_module = ReconnectingWebSocketModule()

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.get_authorized_websocket_uri",
        lambda access_token, timeout_seconds: "wss://example.test/feed",
    )

    feed = make_feed(websocket_module)

    # Simulate the existing live connection and subscription state.
    feed._ws = first_socket
    feed._subscribed_symbols = {"RELIANCE", "TCS"}

    # Reconnect without waiting in the unit test.
    feed.config = UpstoxFeedConfig(
        access_token="test-token",
        mode="ltpc",
        timeout_seconds=7.5,
        reconnect_max_attempts=1,
        reconnect_delay_seconds=0,
    )

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.time.sleep",
        lambda _: None,
    )

    result = feed._reconnect()

    assert result is True
    assert feed.connected is True
    assert feed._ws is second_socket

    # Reconnect must restore both subscriptions.
    assert len(second_socket.sent) == 1

    payload = second_socket.sent[0]["payload"]

    assert b"NSE_EQ|RELIANCE" in payload
    assert b"NSE_EQ|TCS" in payload

    assert feed._subscribed_symbols == {
        "RELIANCE",
        "TCS",
    }


def test_reconnect_returns_false_after_all_attempts_fail(monkeypatch):
    """Reconnect should fail cleanly after exhausting retry attempts."""

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)

    feed = make_feed(websocket_module)

    feed._ws = websocket
    feed._subscribed_symbols = {"RELIANCE"}

    feed.config = UpstoxFeedConfig(
        access_token="test-token",
        mode="ltpc",
        timeout_seconds=7.5,
        reconnect_max_attempts=2,
        reconnect_delay_seconds=0,
    )

    attempts = {"count": 0}

    def fail_connection(access_token, timeout_seconds):
        """Simulate authorization failure on every reconnect attempt."""

        attempts["count"] += 1

        raise RuntimeError("simulated reconnect failure")

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.get_authorized_websocket_uri",
        fail_connection,
    )

    monkeypatch.setattr(
        "market.data.ingestion.providers.upstox.feed.time.sleep",
        lambda _: None,
    )

    result = feed._reconnect()

    assert result is False
    assert attempts["count"] == 2
    assert feed.connected is False

def test_events_records_connection_failure_before_reconnect(monkeypatch):
    """Connection failures should be recorded before reconnecting."""

    from market.data.metrics import DataQualityMetrics

    websocket = FakeWebSocket()
    websocket_module = FakeWebSocketModule(websocket)
    metrics = DataQualityMetrics()

    feed = UpstoxMarketFeed(
        make_config(),
        make_mapper(),
        websocket_module=websocket_module,
        metrics=metrics,
    )

    feed._ws = websocket

    # The events() method requires a protobuf module before reading frames.
    # A dummy object is sufficient because reconnect will be forced to fail.
    feed._protobuf_module = object()

    def raise_connection_error():
        """Simulate a real WebSocket connection failure."""
        raise ConnectionError("simulated connection failure")

    monkeypatch.setattr(
        websocket,
        "recv",
        raise_connection_error,
    )

    # Prevent the test from performing an actual reconnect.
    monkeypatch.setattr(
        feed,
        "_reconnect",
        lambda: False,
    )

    with pytest.raises(
        RuntimeError,
        match="reconnect attempts exhausted",
    ):
        list(feed.events())

    snapshot = metrics.snapshot()

    assert snapshot.connection_failures == 1

def test_events_validate_and_record_metrics():
    """Valid events should be yielded and recorded by the metrics layer."""

    from market.data.ingestion.providers.upstox.generated import (
        MarketDataFeedV3_pb2,
    )
    from market.data.metrics import DataQualityMetrics
    from market.data.validation import MarketEventValidator

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
    metrics = DataQualityMetrics()
    validator = MarketEventValidator(
        max_event_age_seconds=10_000_000_000,
    )

    market_feed = UpstoxMarketFeed(
        make_config(),
        make_mapper(),
        protobuf_module=MarketDataFeedV3_pb2,
        websocket_module=websocket_module,
        event_validator=validator,
        metrics=metrics,
    )

    market_feed._ws = websocket
    market_feed._subscribed_symbols.add("RELIANCE")

    events = list(market_feed.events())

    assert len(events) == 1

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 1
    assert snapshot.events_accepted == 1
    assert snapshot.events_rejected == 0
    assert snapshot.latency_sample_count == 1


def test_invalid_event_is_filtered_and_recorded():
    """Rejected events must not reach downstream consumers."""

    from market.data.ingestion.providers.upstox.generated import (
        MarketDataFeedV3_pb2,
    )
    from market.data.metrics import DataQualityMetrics
    from market.data.validation import MarketEventValidator

    response = MarketDataFeedV3_pb2.FeedResponse()
    response.type = MarketDataFeedV3_pb2.live_feed

    feed = response.feeds["NSE_EQ|RELIANCE"]
    feed.ltpc.ltp = 1425.30
    feed.ltpc.ltt = 1_600_000_000_000
    feed.ltpc.ltq = 125

    websocket = FakeWebSocket()
    websocket.messages = [
        response.SerializeToString(),
        None,
    ]

    websocket_module = FakeWebSocketModule(websocket)

    metrics = DataQualityMetrics()

    # The timestamp above is intentionally stale relative to the
    # validator's configured freshness window.
    validator = MarketEventValidator(
        max_event_age_seconds=5.0,
    )

    market_feed = UpstoxMarketFeed(
        make_config(),
        make_mapper(),
        protobuf_module=MarketDataFeedV3_pb2,
        websocket_module=websocket_module,
        event_validator=validator,
        metrics=metrics,
    )

    market_feed._ws = websocket
    market_feed._subscribed_symbols.add("RELIANCE")

    events = list(market_feed.events())

    # The stale event must be filtered before reaching consumers.
    assert events == []

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 1
    assert snapshot.events_accepted == 0
    assert snapshot.events_rejected == 1
