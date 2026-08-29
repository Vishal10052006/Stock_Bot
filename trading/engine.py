"""
Stock Bot — Paper Trading Engine

Executes approved strategy decisions in paper-trading mode only.
"""

from strategies.models import StrategyDecision
from trading.models import PaperOrder


def create_paper_order(
    strategy: StrategyDecision,
    quantity: int,
    price: float,
    timestamp,
) -> PaperOrder:
    """Create a validated paper-trading order from an approved strategy."""

    return PaperOrder(
        symbol=strategy.symbol,
        side=strategy.action,
        quantity=quantity,
        price=price,
        timestamp=timestamp,
    )
