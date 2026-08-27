"""
Stock Bot — Signal Data Models

Defines the normalized trading signal contract used by
signal generation and downstream strategy components.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class TradingSignal:
    """Represents a normalized trading signal."""

    symbol: str
    signal: Signal
    confidence: float
    timestamp: datetime
    source: str

    def __post_init__(self):
        """Validate the trading signal contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.signal not in ("BUY", "SELL", "HOLD"):
            raise ValueError("signal must be BUY, SELL, or HOLD")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        if not self.source:
            raise ValueError("source must not be empty")
