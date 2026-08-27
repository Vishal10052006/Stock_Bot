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
