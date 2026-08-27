"""
Tests for the Yahoo Finance market-data adapter.

The tests mock the yfinance boundary so they never require
network access or a live Yahoo Finance response.
"""

import pytest

from market_data.adapters.yfinance import YFinancePriceFetcher


class FakeHistory:
    """Minimal fake historical-data object."""

    empty = False

    def __getitem__(self, key):
        """Return fake closing-price data."""

        assert key == "Close"
        return FakeCloseColumn()


class FakeCloseColumn:
    """Minimal fake Close column."""

    def dropna(self):
        """Return the cleaned fake column."""

        return self

    def tolist(self):
        """Return deterministic closing prices."""

        return [2500.0, 2525.5, 2550.0]


class FakeTicker:
    """Fake yfinance ticker used for unit testing."""

    def __init__(self, symbol):
        """Store the requested symbol."""

        assert symbol == "RELIANCE"

    def history(self, **kwargs):
        """Return deterministic historical data."""

        assert kwargs["period"] == "1mo"
        assert kwargs["interval"] == "1d"
        assert kwargs["auto_adjust"] is False

        return FakeHistory()


def test_yfinance_fetcher_returns_close_prices(monkeypatch):
    """Fetcher should return normalized closing prices."""

    import market_data.adapters.yfinance as adapter

    monkeypatch.setattr(adapter.yf, "Ticker", FakeTicker)

    fetcher = YFinancePriceFetcher()

    result = fetcher.fetch_prices("RELIANCE")

    assert result == (2500.0, 2525.5, 2550.0)


def test_yfinance_fetcher_rejects_empty_symbol():
    """An empty symbol should be rejected before yfinance access."""

    fetcher = YFinancePriceFetcher()

    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        fetcher.fetch_prices("")


def test_yfinance_fetcher_rejects_empty_history(monkeypatch):
    """Empty Yahoo Finance history should be rejected."""

    import market_data.adapters.yfinance as adapter

    class EmptyHistory:
        """Fake empty history response."""

        empty = True

    class EmptyTicker:
        """Fake ticker returning empty history."""

        def history(self, **kwargs):
            """Return an empty response."""

            return EmptyHistory()

    monkeypatch.setattr(
        adapter.yf,
        "Ticker",
        lambda symbol: EmptyTicker(),
    )

    fetcher = YFinancePriceFetcher()

    with pytest.raises(
        ValueError,
        match="returned no data",
    ):
        fetcher.fetch_prices("RELIANCE")


def test_yfinance_fetcher_translates_external_failure(monkeypatch):
    """External yfinance failures should become RuntimeError."""

    import market_data.adapters.yfinance as adapter

    class FailingTicker:
        """Fake ticker that simulates a network failure."""

        def history(self, **kwargs):
            """Raise an external provider error."""

            raise ConnectionError("network unavailable")

    monkeypatch.setattr(
        adapter.yf,
        "Ticker",
        lambda symbol: FailingTicker(),
    )

    fetcher = YFinancePriceFetcher()

    with pytest.raises(
        RuntimeError,
        match="Yahoo Finance request failed",
    ):
        fetcher.fetch_prices("RELIANCE")


def test_yfinance_fetcher_rejects_non_finite_prices(monkeypatch):
    """NaN and infinity should never cross the provider boundary."""

    import market_data.adapters.yfinance as adapter

    class NonFiniteCloseColumn:
        """Fake Close column containing a non-finite value."""

        def dropna(self):
            """Return the fake cleaned column."""

            return self

        def tolist(self):
            """Return invalid non-finite prices."""

            return [2500.0, float("nan")]

    class NonFiniteHistory:
        """Fake history containing a non-finite close."""

        empty = False

        def __getitem__(self, key):
            """Return the fake Close column."""

            assert key == "Close"
            return NonFiniteCloseColumn()

    class NonFiniteTicker:
        """Fake ticker returning non-finite market data."""

        def history(self, **kwargs):
            """Return the invalid history."""

            return NonFiniteHistory()

    monkeypatch.setattr(
        adapter.yf,
        "Ticker",
        lambda symbol: NonFiniteTicker(),
    )

    fetcher = YFinancePriceFetcher()

    with pytest.raises(
        ValueError,
        match="non-finite prices",
    ):
        fetcher.fetch_prices("RELIANCE")
