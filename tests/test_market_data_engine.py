"""
Tests for the Market Data Engine.

Verifies provider injection, normalization, and validation.
"""

from datetime import datetime

import pytest

from market_data.engine import MarketDataEngine


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


class FakeMarketDataProvider:
    """Deterministic provider used for unit testing."""

    def get_prices(self, symbol):
        """Return fixed prices for the requested symbol."""

        assert symbol == "RELIANCE"

        return [2500.0, 2510.0, 2520.0]


class EmptyMarketDataProvider:
    """Provider that simulates an empty market-data response."""

    def get_prices(self, symbol):
        """Return no prices."""

        return []


def test_market_data_engine_uses_provider():
    """Provider prices should become normalized MarketPrice objects."""

    engine = MarketDataEngine(FakeMarketDataProvider())

    result = engine.get_prices(
        symbol="RELIANCE",
        timestamp=TIMESTAMP,
    )

    assert len(result) == 3

    assert result[0].symbol == "RELIANCE"
    assert result[0].price == 2500.0
    assert result[1].price == 2510.0
    assert result[2].price == 2520.0

    assert result[0].timestamp == TIMESTAMP


def test_empty_symbol_is_rejected():
    """An empty symbol should be rejected before provider access."""

    class ProviderThatMustNotBeCalled:
        """Provider used to verify early validation."""

        def get_prices(self, symbol):
            """Fail if the engine calls the provider."""
            raise AssertionError("provider should not be called")

    engine = MarketDataEngine(
        ProviderThatMustNotBeCalled()
    )

    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        engine.get_prices(
            symbol="",
            timestamp=TIMESTAMP,
        )


def test_empty_provider_result_is_rejected():
    """An empty provider response should be rejected."""

    engine = MarketDataEngine(
        EmptyMarketDataProvider()
    )

    with pytest.raises(
        ValueError,
        match="price provider returned no prices",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )


class ConfigurableMarketDataProvider:
    """Provider that returns caller-supplied test prices."""

    def __init__(self, prices):
        """Store the prices that should be returned."""
        self.prices = prices

    def get_prices(self, symbol):
        """Return the configured test prices."""
        return self.prices


def test_non_numeric_provider_price_is_rejected():
    """Non-numeric provider output should be rejected."""

    provider = ConfigurableMarketDataProvider(
        ["not-a-price"]
    )
    engine = MarketDataEngine(provider)

    with pytest.raises(
        ValueError,
        match="non-numeric price",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )


def test_non_positive_provider_price_is_rejected():
    """Zero or negative provider output should be rejected."""

    provider = ConfigurableMarketDataProvider(
        [0, -10]
    )
    engine = MarketDataEngine(provider)

    with pytest.raises(
        ValueError,
        match="non-positive price",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )


def test_non_finite_provider_price_is_rejected():
    """NaN and infinite provider output should be rejected."""

    provider = ConfigurableMarketDataProvider(
        [float("nan")]
    )
    engine = MarketDataEngine(provider)

    with pytest.raises(
        ValueError,
        match="non-finite price",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )


def test_infinite_provider_price_is_rejected():
    """Infinite provider output should be rejected."""

    provider = ConfigurableMarketDataProvider(
        [float("inf")]
    )
    engine = MarketDataEngine(provider)

    with pytest.raises(
        ValueError,
        match="non-finite price",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )
