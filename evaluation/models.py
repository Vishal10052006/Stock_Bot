"""
Stock Bot — Evaluation Data Models

Defines the normalized trade-performance evaluation contract.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeEvaluation:
    """Represents the evaluated outcome of a paper trade."""

    symbol: str
    pnl: float
    return_pct: float
    holding_period_minutes: int
    success: bool

    def __post_init__(self):
        """Validate the trade-evaluation contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.holding_period_minutes < 0:
            raise ValueError("holding period must not be negative")
