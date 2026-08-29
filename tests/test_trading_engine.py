"""
Tests for the Stock Bot paper-trading engine.
"""

from datetime import datetime

from strategies.models import StrategyDecision
from trading.engine import create_paper_order


def test_buy_strategy_creates_paper_order():
    """A BUY strategy should create a valid paper order."""

    strategy = StrategyDecision(
        symbol="RELIANCE",
        action="BUY",
        confidence=0.85,
        rationale="Positive technical setup.",
    )

    order = create_paper_order(
        strategy=strategy,
        quantity=10,
        price=2500.0,
        timestamp=datetime(2026, 8, 27, 9, 30),
    )

    assert order.symbol == "RELIANCE"
    assert order.side == "BUY"
    assert order.quantity == 10
    assert order.price == 2500.0


def test_sell_strategy_creates_paper_order():
    """A SELL strategy should create a valid paper order."""

    strategy = StrategyDecision(
        symbol="RELIANCE",
        action="SELL",
        confidence=0.80,
        rationale="Negative technical setup.",
    )

    order = create_paper_order(
        strategy=strategy,
        quantity=5,
        price=2510.0,
        timestamp=datetime(2026, 8, 27, 9, 30),
    )

    assert order.side == "SELL"
    assert order.quantity == 5
