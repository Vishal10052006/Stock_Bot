"""
Stock Bot - Market Data Providers

Contains concrete implementations of the MarketDataProvider contract.

Phase 1 intentionally uses a deterministic in-memory provider so that
the market-data pipeline can be tested without network calls,
API credentials, rate limits, or external service failures.
"""

from typing import Sequence


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
