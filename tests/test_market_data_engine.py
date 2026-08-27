"""
Tests for the Market Data Engine.

Verifies provider injection, normalization, and validation.
"""

from datetime import datetime

import pytest

from market_data.engine import MarketDataEngine


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


def test_market_data_engine_normalizes_provider_prices():
    """Provider prices should become MarketPrice objects."""

    def fake_provider(symbol):
        """Return deterministic test prices."""
        assert symbol == "RELIANCE"
        return [2500.0, 2510.0, 2520.0]

    engine = MarketDataEngine(fake_provider)

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

    def fake_provider(symbol):
        """This provider should never be called."""
        raise AssertionError("provider should not be called")

    engine = MarketDataEngine(fake_provider)

    with pytest.raises(ValueError, match="symbol must not be empty"):
        engine.get_prices(
            symbol="",
            timestamp=TIMESTAMP,
        )


def test_empty_provider_result_is_rejected():
    """An empty provider response should be rejected."""

    def fake_provider(symbol):
        """Return no market data."""
        return []

    engine = MarketDataEngine(fake_provider)

    with pytest.raises(
        ValueError,
        match="price provider returned no prices",
    ):
        engine.get_prices(
            symbol="RELIANCE",
            timestamp=TIMESTAMP,
        )
