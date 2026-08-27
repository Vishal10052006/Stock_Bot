"""
Stock Bot — Strategy Data Models

Defines the normalized strategy decision contract used by
the strategy and risk layers.
"""

from dataclasses import dataclass
from typing import Literal


Action = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class StrategyDecision:
    """Represents a strategy decision before risk approval."""

    symbol: str
    action: Action
    confidence: float
    rationale: str

    def __post_init__(self):
        """Validate the strategy decision contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.action not in ("BUY", "SELL", "HOLD"):
            raise ValueError("action must be BUY, SELL, or HOLD")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        if not self.rationale:
            raise ValueError("rationale must not be empty")
