"""
Stock Bot — Evaluation Engine

Evaluates paper-trade outcomes using the normalized
trade-evaluation contract.
"""

from evaluation.models import TradeEvaluation


def evaluate_trade(
    symbol: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    holding_period_minutes: int,
) -> TradeEvaluation:
    """Calculate P&L and return percentage for a paper trade."""

    if entry_price <= 0:
        raise ValueError("entry_price must be greater than zero")

    if exit_price <= 0:
        raise ValueError("exit_price must be greater than zero")

    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")

    pnl = (exit_price - entry_price) * quantity
    return_pct = ((exit_price - entry_price) / entry_price) * 100.0

    return TradeEvaluation(
        symbol=symbol,
        pnl=pnl,
        return_pct=return_pct,
        holding_period_minutes=holding_period_minutes,
        success=pnl > 0,
    )
