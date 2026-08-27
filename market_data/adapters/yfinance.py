"""
Stock Bot - Yahoo Finance Market Data Adapter

Provides a small yfinance-specific fetch boundary.

The rest of Stock Bot must not depend directly on yfinance.
"""

from collections.abc import Sequence
from math import isfinite

import yfinance as yf


class YFinancePriceFetcher:
    """
    Retrieve historical closing prices through yfinance.

    This class contains the only direct dependency on yfinance.
    """

    def __init__(
        self,
        period: str = "1mo",
        interval: str = "1d",
    ):
        """
        Initialize the Yahoo Finance fetcher.

        Args:
            period: Historical period requested from Yahoo Finance.
            interval: Price interval requested from Yahoo Finance.
        """

        if not period:
            raise ValueError("period must not be empty")

        if not interval:
            raise ValueError("interval must not be empty")

        self.period = period
        self.interval = interval

    def fetch_prices(self, symbol: str) -> Sequence[float]:
        """
        Fetch historical closing prices for a symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            A sequence of closing prices.

        Raises:
            ValueError: If the symbol is empty or no data is returned.
            RuntimeError: If the external market-data request fails.
        """

        if not symbol:
            raise ValueError("symbol must not be empty")

        try:
            ticker = yf.Ticker(symbol)

            # Download historical market data from Yahoo Finance.
            history = ticker.history(
                period=self.period,
                interval=self.interval,
                auto_adjust=False,
            )
        except Exception as exc:
            # Keep yfinance-specific exceptions inside the adapter boundary.
            raise RuntimeError(
                f"Yahoo Finance request failed for {symbol}"
            ) from exc

        if history is None or history.empty:
            raise ValueError(
                f"Yahoo Finance returned no data for {symbol}"
            )

        try:
            prices = tuple(
                float(price)
                for price in history["Close"].dropna().tolist()
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Yahoo Finance returned invalid close prices for {symbol}"
            ) from exc

        if not prices:
            raise ValueError(
                f"Yahoo Finance returned no valid close prices for {symbol}"
            )

        if any(not isfinite(price) for price in prices):
            raise ValueError(
                f"Yahoo Finance returned non-finite prices for {symbol}"
            )

        if any(price <= 0 for price in prices):
            raise ValueError(
                f"Yahoo Finance returned non-positive prices for {symbol}"
            )

        return prices
