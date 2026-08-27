"""
Tests for the Phase-1 market-data provider adapter.

Verifies that the concrete provider satisfies the expected
MarketDataProvider behavior.
"""

from market_data.providers import StaticMarketDataProvider


def test_static_provider_returns_configured_prices():
    """The provider should return its configured prices."""

    provider = StaticMarketDataProvider(
        prices=[2500.0, 2525.0, 2550.0]
    )

    result = provider.get_prices("RELIANCE")

    assert list(result) == [2500.0, 2525.0, 2550.0]


def test_static_provider_normalizes_prices_to_float():
    """Configured numeric values should be exposed as floats."""

    provider = StaticMarketDataProvider(
        prices=[2500, 2525]
    )

    result = provider.get_prices("RELIANCE")

    assert list(result) == [2500.0, 2525.0]


def test_static_provider_returns_empty_sequence_when_configured_empty():
    """An empty provider configuration should remain empty."""

    provider = StaticMarketDataProvider(prices=[])

    result = provider.get_prices("RELIANCE")

    assert list(result) == []
