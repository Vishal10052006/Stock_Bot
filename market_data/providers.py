"""
Stock Bot - Market Data Providers

Defines the provider contract and concrete market-data providers.

The rest of the system depends on the MarketDataProvider contract
rather than on a specific external market-data service.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketDataProvider(Protocol):
    """
    Contract that every market-data provider must implement.

    A provider is responsible only for retrieving raw price
    observations. Normalization into domain models is handled
    elsewhere by MarketDataEngine.
    """

    def get_prices(self, symbol: str) -> Sequence[float]:
        """Return raw price observations for a stock symbol."""
        ...


class StaticMarketDataProvider:
    """
    Deterministic market-data provider for testing and development.

    The provider returns a predefined sequence of prices regardless
    of the requested symbol.
    """

    def __init__(self, prices: Sequence[float]):
        """
        Initialize the provider with predefined prices.

        Args:
            prices: Price observations to return to callers.
        """

        # Copy the input so external mutation cannot alter provider state.
        self._prices = tuple(float(price) for price in prices)

    def get_prices(self, symbol: str) -> Sequence[float]:
        """
        Return the configured price observations.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            A deterministic sequence of market prices.
        """

        # Phase 1 does not need symbol-specific storage yet.
        return self._prices
