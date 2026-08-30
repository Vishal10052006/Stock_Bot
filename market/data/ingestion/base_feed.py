"""Provider-independent real-time market feed interface."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from market.data.events import MarketEvent


class MarketFeed(ABC):
    """Contract implemented by every real-time market data provider.

    Provider-specific adapters must translate their native payloads into
    ``MarketEvent`` instances before exposing them to the trading system.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the provider connection."""
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, symbols: Iterable[str]) -> None:
        """Subscribe to the requested symbols."""
        raise NotImplementedError

    @abstractmethod
    def events(self) -> Iterator[MarketEvent]:
        """Yield canonical events from the live feed."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Close the provider connection and release resources."""
        raise NotImplementedError

    def __enter__(self) -> "MarketFeed":
        """Connect automatically when entering a context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Always disconnect when leaving the context."""
        self.disconnect()
