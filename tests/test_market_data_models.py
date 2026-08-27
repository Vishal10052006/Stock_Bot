"""
Tests for the market data contract.

Verifies valid market observations and rejects invalid data.
"""

from datetime import datetime

import pytest

from market_data.models import MarketPrice


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


def test_valid_market_price_is_created():
    """A valid market price should be accepted."""

    result = MarketPrice(
        symbol="RELIANCE",
        price=2500.0,
        timestamp=TIMESTAMP,
    )

    assert result.symbol == "RELIANCE"
    assert result.price == 2500.0
    assert result.timestamp == TIMESTAMP


def test_empty_symbol_is_rejected():
    """An empty symbol should be rejected."""

    with pytest.raises(ValueError):
        MarketPrice(
            symbol="",
            price=2500.0,
            timestamp=TIMESTAMP,
        )


def test_non_positive_price_is_rejected():
    """Zero or negative prices should be rejected."""

    with pytest.raises(ValueError):
        MarketPrice(
            symbol="RELIANCE",
            price=0,
            timestamp=TIMESTAMP,
        )
