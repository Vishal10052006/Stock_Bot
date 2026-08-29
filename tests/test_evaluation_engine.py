"""
Tests for Stock Bot evaluation engine.
"""

import pytest

from evaluation.engine import evaluate_trade


def test_profitable_trade_is_evaluated_successfully():
    """A profitable paper trade should produce positive P&L."""

    result = evaluate_trade(
        symbol="RELIANCE",
        entry_price=2500.0,
        exit_price=2550.0,
        quantity=10,
        holding_period_minutes=30,
    )

    assert result.symbol == "RELIANCE"
    assert result.pnl == 500.0
    assert result.return_pct == 2.0
    assert result.holding_period_minutes == 30
    assert result.success is True


def test_losing_trade_is_evaluated_as_failure():
    """A losing paper trade should produce negative P&L."""

    result = evaluate_trade(
        symbol="RELIANCE",
        entry_price=2500.0,
        exit_price=2450.0,
        quantity=10,
        holding_period_minutes=45,
    )

    assert result.pnl == -500.0
    assert result.return_pct == -2.0
    assert result.success is False


def test_zero_quantity_is_rejected():
    """Zero quantity should not be accepted."""

    with pytest.raises(ValueError):
        evaluate_trade(
            symbol="RELIANCE",
            entry_price=2500.0,
            exit_price=2550.0,
            quantity=0,
            holding_period_minutes=30,
        )


def test_invalid_entry_price_is_rejected():
    """Non-positive entry prices should be rejected."""

    with pytest.raises(ValueError):
        evaluate_trade(
            symbol="RELIANCE",
            entry_price=0,
            exit_price=2550.0,
            quantity=10,
            holding_period_minutes=30,
        )


def test_invalid_exit_price_is_rejected():
    """Non-positive exit prices should be rejected."""

    with pytest.raises(ValueError):
        evaluate_trade(
            symbol="RELIANCE",
            entry_price=2500.0,
            exit_price=0,
            quantity=10,
            holding_period_minutes=30,
        )
