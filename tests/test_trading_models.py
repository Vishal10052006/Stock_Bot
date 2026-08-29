"""
Tests for Stock Bot paper-trading data contracts.
"""

from datetime import datetime

import pytest

from trading.models import PaperOrder


def test_valid_paper_order():
    """A valid paper order should be accepted."""

    order = PaperOrder(
        symbol="RELIANCE",
        side="BUY",
        quantity=10,
        price=2500.0,
        timestamp=datetime(2026, 8, 27, 9, 30),
    )

    assert order.symbol == "RELIANCE"
    assert order.side == "BUY"
    assert order.quantity == 10


def test_invalid_side_is_rejected():
    """Unsupported order sides should be rejected."""

    with pytest.raises(ValueError):
        PaperOrder(
            symbol="RELIANCE",
            side="HOLD",
            quantity=10,
            price=2500.0,
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_invalid_quantity_is_rejected():
    """Non-positive quantities should be rejected."""

    with pytest.raises(ValueError):
        PaperOrder(
            symbol="RELIANCE",
            side="BUY",
            quantity=0,
            price=2500.0,
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_invalid_price_is_rejected():
    """Non-positive prices should be rejected."""

    with pytest.raises(ValueError):
        PaperOrder(
            symbol="RELIANCE",
            side="BUY",
            quantity=10,
            price=0,
            timestamp=datetime(2026, 8, 27, 9, 30),
        )
