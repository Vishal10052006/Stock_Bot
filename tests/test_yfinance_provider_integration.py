"""
Integration tests for the yfinance provider path.

The external network is still mocked. This verifies the architecture:

YFinancePriceFetcher
    -> ExternalMarketDataProvider
    -> MarketDataProvider contract
"""
from market_data.adapters.external import ExternalMarketDataProvider
from market_data.adapters.yfinance import YFinancePriceFetcher
from market_data.providers import MarketDataProvider


def test_yfinance_fetcher_can_feed_external_provider(monkeypatch):
    """YFinance fetcher should work through the external provider adapter."""

    import market_data.adapters.yfinance as yfinance_adapter

    class FakeHistory:
        """Minimal deterministic historical-data response."""

        empty = False

        def __getitem__(self, key):
            """Return the fake Close column."""

            assert key == "Close"
            return self

        def dropna(self):
            """Return the cleaned fake column."""

            return self

        def tolist(self):
            """Return deterministic closing prices."""

            return [2500.0, 2525.0, 2550.0]

    class FakeTicker:
        """Fake Yahoo Finance ticker."""

        def __init__(self, symbol):
            """Validate the requested ticker."""

            assert symbol == "RELIANCE"

        def history(self, **kwargs):
            """Return deterministic historical data."""

            return FakeHistory()

    monkeypatch.setattr(
        yfinance_adapter.yf,
        "Ticker",
        FakeTicker,
    )

    fetcher = YFinancePriceFetcher(
        period="1mo",
        interval="1d",
    )

    provider = ExternalMarketDataProvider(
        fetcher.fetch_prices,
    )

    assert isinstance(provider, MarketDataProvider)

    result = provider.get_prices("RELIANCE")

    assert result == (
        2500.0,
        2525.0,
        2550.0,
    )


def test_yfinance_provider_can_feed_market_data_engine(monkeypatch):
    """The complete provider chain should produce normalized market data."""

    from datetime import datetime

    import market_data.adapters.yfinance as yfinance_adapter
    from market_data.engine import MarketDataEngine

    class FakeHistory:
        """Minimal deterministic historical-data response."""

        empty = False

        def __getitem__(self, key):
            """Return the fake Close column."""

            assert key == "Close"
            return self

        def dropna(self):
            """Return the cleaned fake column."""

            return self

        def tolist(self):
            """Return deterministic closing prices."""

            return [2500.0, 2550.0]

    class FakeTicker:
        """Fake Yahoo Finance ticker."""

        def history(self, **kwargs):
            """Return deterministic historical data."""

            return FakeHistory()

    monkeypatch.setattr(
        yfinance_adapter.yf,
        "Ticker",
        lambda symbol: FakeTicker(),
    )

    fetcher = YFinancePriceFetcher(
        period="1mo",
        interval="1d",
    )

    provider = ExternalMarketDataProvider(
        fetcher.fetch_prices,
    )

    engine = MarketDataEngine(provider)

    timestamp = datetime(2026, 8, 27, 9, 30)

    result = engine.get_prices(
        symbol="RELIANCE",
        timestamp=timestamp,
    )

    assert len(result) == 2
    assert result[0].symbol == "RELIANCE"
    assert result[0].price == 2500.0
    assert result[1].price == 2550.0
    assert result[0].timestamp == timestamp
