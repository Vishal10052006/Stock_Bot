"""
Stock Bot - Market Data Engine

Provides a provider-independent interface for obtaining normalized
market prices.

The engine depends on a narrow provider contract rather than on a
specific external market-data service.
"""

from datetime import datetime
from typing import Protocol, Sequence

from market_data.models import MarketPrice


class MarketDataProvider(Protocol):
    """Contract that every market-data provider must implement."""

    def get_prices(self, symbol: str) -> Sequence[float]:
        """Return raw price observations for a stock symbol."""
        ...


class MarketDataEngine:
    """Normalize provider data into Stock Bot market-data contracts."""

    def __init__(self, provider: MarketDataProvider):
        """
        Initialize the market-data engine.

        Args:
            provider: Object implementing the MarketDataProvider contract.
        """

        # Keep the external data source behind a stable abstraction.
        self.provider = provider

    def get_prices(
        self,
        symbol: str,
        timestamp: datetime,
    ) -> list[MarketPrice]:
        """
        Fetch and normalize market prices.

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

        # Obtain raw prices through the provider contract.
        prices = self.provider.get_prices(symbol)

        if not prices:
            raise ValueError("price provider returned no prices")

        # Convert provider output into domain-level contracts.
        return [
            MarketPrice(
                symbol=symbol,
                price=float(price),
                timestamp=timestamp,
            )
            for price in prices
        ]
