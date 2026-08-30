"""Tests for the provider-independent Phase 3.1 feed contract."""

from collections.abc import Iterator

from market.data.events import MarketEvent
from market.data.ingestion import MarketFeed


class StubMarketFeed(MarketFeed):
    """Minimal provider stub used to verify the interface contract."""

    def __init__(self) -> None:
        self.is_connected = False
        self.subscribed: list[str] = []
        self.is_disconnected = False

    def connect(self) -> None:
        """Record a connection request."""
        self.is_connected = True

    def subscribe(self, symbols) -> None:
        """Record requested subscriptions."""
        self.subscribed.extend(symbols)

    def events(self) -> Iterator[MarketEvent]:
        """Return an empty stream for the test provider."""
        yield from ()

    def disconnect(self) -> None:
        """Record a disconnect request."""
        self.is_disconnected = True


def test_market_feed_context_manager_connects_and_disconnects():
    """The feed context manager must always clean up the connection."""
    feed = StubMarketFeed()

    with feed as active_feed:
        assert active_feed is feed
        assert feed.is_connected is True

    assert feed.is_disconnected is True


def test_market_feed_is_abstract():
    """Provider implementations must implement every feed operation."""
    try:
        MarketFeed()
    except TypeError:
        pass
    else:
        raise AssertionError("MarketFeed should be abstract")
