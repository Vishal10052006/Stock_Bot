"""
Stock Bot - Market Data Engine

Provides a provider-independent interface for obtaining normalized
market prices.

The engine depends on the MarketDataProvider contract rather than
on a specific external market-data service.
"""

from datetime import datetime
from math import isfinite

from market_data.models import MarketPrice
from market_data.providers import MarketDataProvider


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
            ValueError: If the symbol is empty, the provider returns
                no prices, or a provider price is invalid.
        """

        if not symbol:
            raise ValueError("symbol must not be empty")

        # Obtain raw prices through the provider contract.
        prices = self.provider.get_prices(symbol)

        if not prices:
            raise ValueError("price provider returned no prices")

        normalized_prices: list[float] = []

        for price in prices:
            try:
                normalized_price = float(price)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "price provider returned a non-numeric price"
                ) from exc

            # Reject NaN and infinite values before creating domain objects.
            if not isfinite(normalized_price):
                raise ValueError(
                    "price provider returned a non-finite price"
                )

            if normalized_price <= 0:
                raise ValueError(
                    "price provider returned a non-positive price"
                )

            normalized_prices.append(normalized_price)

        # Convert validated provider output into domain-level contracts.
        return [
            MarketPrice(
                symbol=symbol,
                price=price,
                timestamp=timestamp,
            )
            for price in normalized_prices
        ]
