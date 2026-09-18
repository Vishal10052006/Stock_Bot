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


def test_fractional_quantity_is_rejected():
    """Fractional quantities must not pass the integer order contract."""

    with pytest.raises(ValueError, match="quantity must be an integer"):
        PaperOrder(
            symbol="RELIANCE",
            side="BUY",
            quantity=0.5,
            price=2500.0,
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_non_finite_price_is_rejected():
    """NaN and infinity must not enter paper execution."""

    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="price must be finite"):
            PaperOrder(
                symbol="RELIANCE",
                side="BUY",
                quantity=10,
                price=value,
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
