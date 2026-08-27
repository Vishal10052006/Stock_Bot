"""
Tests for Stock Bot trade-evaluation data contracts.
"""

import pytest

from evaluation.models import TradeEvaluation


def test_valid_trade_evaluation():
    """A valid trade evaluation should be accepted."""

    result = TradeEvaluation(
        symbol="RELIANCE",
        pnl=250.0,
        return_pct=1.0,
        holding_period_minutes=30,
        success=True,
    )

    assert result.symbol == "RELIANCE"
    assert result.pnl == 250.0
    assert result.success is True


def test_negative_pnl_is_allowed():
    """A losing trade should still be a valid evaluation."""

    result = TradeEvaluation(
        symbol="RELIANCE",
        pnl=-150.0,
        return_pct=-0.6,
        holding_period_minutes=20,
        success=False,
    )

    assert result.pnl == -150.0
    assert result.success is False


def test_negative_holding_period_is_rejected():
    """Holding period cannot be negative."""

    with pytest.raises(ValueError):
        TradeEvaluation(
            symbol="RELIANCE",
            pnl=100.0,
            return_pct=0.4,
            holding_period_minutes=-1,
            success=True,
        )
