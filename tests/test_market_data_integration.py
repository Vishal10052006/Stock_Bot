"""
Integration tests for the Phase-1 market-data pipeline.

Verifies that a MarketDataProvider can feed the MarketDataEngine
and produce data suitable for the existing Stock Bot pipeline.
"""

from datetime import datetime

from market_data.engine import MarketDataEngine
from market_data.providers import StaticMarketDataProvider


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


def test_provider_flows_into_market_data_engine():
    """Provider data should be normalized by MarketDataEngine."""

    provider = StaticMarketDataProvider(
        prices=[2500.0, 2550.0]
    )

    engine = MarketDataEngine(provider)

    result = engine.get_prices(
        symbol="RELIANCE",
        timestamp=TIMESTAMP,
    )

    assert len(result) == 2
    assert result[0].price == 2500.0
    assert result[1].price == 2550.0
    assert result[0].symbol == "RELIANCE"
    assert result[0].timestamp == TIMESTAMP


def test_market_data_output_can_feed_feature_pipeline():
    """Normalized market prices should provide usable feature inputs."""

    provider = StaticMarketDataProvider(
        prices=[2500.0, 2550.0]
    )

    engine = MarketDataEngine(provider)

    result = engine.get_prices(
        symbol="RELIANCE",
        timestamp=TIMESTAMP,
    )

    prices = [market_price.price for market_price in result]

    assert prices == [2500.0, 2550.0]
