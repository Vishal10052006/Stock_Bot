"""
Stock Bot - Market Data Engine

Provides a provider-independent interface for obtaining normalized
market prices.

The engine deliberately does not depend on a specific market-data
provider. A provider can be connected later without changing the
downstream trading pipeline.
"""

from datetime import datetime
from typing import Callable, Sequence

from market_data.models import MarketPrice


class MarketDataEngine:
    """Normalize market-price data for the Stock Bot."""

    def __init__(self, price_provider: Callable[[str], Sequence[float]]):
        """
        Initialize the market-data engine.

        Args:
            price_provider: Callable that receives a symbol and returns
                a sequence of positive historical/current prices.
        """

        # Keep the external provider behind a narrow interface.
        self.price_provider = price_provider

    def get_prices(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> list[MarketPrice]:
        """
        Fetch and normalize prices for a symbol.

        Args:
            symbol: Stock ticker symbol.
            timestamp: Timestamp associated with the observations.

        Returns:
            A list of normalized MarketPrice objects.

        Raises:
            ValueError: If the symbol is empty or no prices are returned.
        """

        if not symbol:
            raise ValueError("symbol must not be empty")

        # Obtain raw prices from the injected provider.
        prices = self.price_provider(symbol)

        if not prices:
            raise ValueError("price provider returned no prices")

        # Convert provider output into the domain contract.
        return [
            MarketPrice(
                symbol=symbol,
                price=float(price),
                timestamp=timestamp,
            )
            for price in prices
        ]
