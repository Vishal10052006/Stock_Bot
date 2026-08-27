"""
Stock Bot - External Market Data Adapter

Provides an adapter boundary for external market-data services.

The adapter intentionally receives its fetch operation through
dependency injection. This keeps the core system independent of
HTTP clients, API credentials, network availability, and provider SDKs.
"""

import math
from collections.abc import Callable, Sequence

from market_data.providers import MarketDataProvider


class MarketDataProviderError(RuntimeError):
    """Raised when an external market-data provider cannot supply data."""


class ExternalMarketDataProvider:
    """
    Adapt an external price-fetching function to MarketDataProvider.

    The injected fetch function is responsible only for retrieving
    raw price observations. Provider-specific SDK/API handling stays
    outside the Stock Bot core.
    """

    def __init__(
        self,
        fetch_prices: Callable[[str], Sequence[float]],
    ):
        """
        Initialize the external provider adapter.

        Args:
            fetch_prices: Callable that retrieves prices for a symbol.
        """

        if not callable(fetch_prices):
            raise TypeError("fetch_prices must be callable")

        # Store the external operation behind a stable adapter boundary.
        self._fetch_prices = fetch_prices

    def get_prices(self, symbol: str) -> Sequence[float]:
        """
        Fetch prices through the external provider boundary.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            A validated sequence of positive, finite prices.

        Raises:
            ValueError: If the symbol is empty.
            MarketDataProviderError: If the external provider fails
                or returns invalid market data.
        """

        if not symbol:
            raise ValueError("symbol must not be empty")

        try:
            prices = self._fetch_prices(symbol)
        except Exception as exc:
            # Prevent provider-specific exceptions from leaking into
            # the rest of the Stock Bot architecture.
            raise MarketDataProviderError(
                f"external market-data provider failed for {symbol}"
            ) from exc

        if not prices:
            raise MarketDataProviderError(
                f"external market-data provider returned no prices for {symbol}"
            )

        try:
            normalized_prices = tuple(
                float(price)
                for price in prices
            )
        except (TypeError, ValueError) as exc:
            # Normalize provider-specific numeric conversion failures
            # into one stable application-level exception.
            raise MarketDataProviderError(
                f"external market-data provider returned invalid prices "
                f"for {symbol}"
            ) from exc

        # Reject NaN and positive/negative infinity before data reaches
        # the core market-data engine.
        if any(
            not math.isfinite(price)
            for price in normalized_prices
        ):
            raise MarketDataProviderError(
                f"external market-data provider returned non-finite "
                f"prices for {symbol}"
            )

        # Market prices must always be strictly positive.
        if any(
            price <= 0
            for price in normalized_prices
        ):
            raise MarketDataProviderError(
                f"external market-data provider returned non-positive "
                f"prices for {symbol}"
            )

        return normalized_prices


# Structural contract check:
# ExternalMarketDataProvider intentionally implements MarketDataProvider.
assert isinstance(
    ExternalMarketDataProvider(lambda symbol: [100.0]),
    MarketDataProvider,
)
