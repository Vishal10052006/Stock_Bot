"""
Tests for the market-data provider contract and static provider.
"""

from market_data.providers import (
    MarketDataProvider,
    StaticMarketDataProvider,
)


def test_static_provider_returns_configured_prices():
    """Static provider should return its configured price sequence."""

    provider = StaticMarketDataProvider(
        [100.0, 101.5, 103.0]
    )

    assert list(provider.get_prices("RELIANCE")) == [
        100.0,
        101.5,
        103.0,
    ]


def test_static_provider_copies_input_prices():
    """External mutation should not alter provider state."""

    prices = [100.0, 101.0]
    provider = StaticMarketDataProvider(prices)

    prices.append(999.0)

    assert list(provider.get_prices("RELIANCE")) == [
        100.0,
        101.0,
    ]


def test_static_provider_satisfies_provider_contract():
    """Static provider should structurally satisfy MarketDataProvider."""

    provider = StaticMarketDataProvider([100.0])

    assert isinstance(provider, MarketDataProvider)
