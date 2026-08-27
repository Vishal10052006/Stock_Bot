"""
Tests for the external market-data provider adapter.

The tests use injected functions instead of real network calls.
"""

import pytest

from market_data.adapters.external import (
    ExternalMarketDataProvider,
    MarketDataProviderError,
)
from market_data.providers import MarketDataProvider


def test_external_provider_returns_fetched_prices():
    """Injected external data should be returned as normalized floats."""

    def fetch_prices(symbol):
        assert symbol == "RELIANCE"
        return [2500, 2525.5]

    provider = ExternalMarketDataProvider(fetch_prices)

    result = provider.get_prices("RELIANCE")

    assert result == (2500.0, 2525.5)


def test_external_provider_satisfies_provider_contract():
    """The external adapter should satisfy MarketDataProvider."""

    provider = ExternalMarketDataProvider(
        lambda symbol: [2500.0]
    )

    assert isinstance(provider, MarketDataProvider)


def test_external_provider_rejects_empty_symbol():
    """An empty symbol should be rejected before calling the provider."""

    provider = ExternalMarketDataProvider(
        lambda symbol: [2500.0]
    )

    with pytest.raises(ValueError):
        provider.get_prices("")


def test_external_provider_translates_provider_failure():
    """External exceptions should become MarketDataProviderError."""

    def fetch_prices(symbol):
        raise ConnectionError("network unavailable")

    provider = ExternalMarketDataProvider(fetch_prices)

    with pytest.raises(MarketDataProviderError):
        provider.get_prices("RELIANCE")


def test_external_provider_rejects_empty_response():
    """An empty external response should be rejected."""

    provider = ExternalMarketDataProvider(
        lambda symbol: []
    )

    with pytest.raises(MarketDataProviderError):
        provider.get_prices("RELIANCE")


def test_external_provider_rejects_invalid_prices():
    """Invalid numeric data should be rejected."""

    provider = ExternalMarketDataProvider(
        lambda symbol: ["invalid"]
    )

    with pytest.raises(MarketDataProviderError):
        provider.get_prices("RELIANCE")


def test_external_provider_rejects_non_positive_prices():
    """Zero or negative external prices should be rejected."""

    provider = ExternalMarketDataProvider(
        lambda symbol: [2500.0, 0.0]
    )

    with pytest.raises(MarketDataProviderError):
        provider.get_prices("RELIANCE")
