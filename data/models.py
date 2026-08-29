"""
Stock Bot — Core Data Models

Defines immutable domain objects shared across the
market-data, signal, strategy, risk, and trading layers.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class MarketBar:
    """Represents one OHLCV market-data bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        """Validate basic OHLCV invariants."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("OHLC prices must be greater than zero")

        if self.volume < 0:
            raise ValueError("volume must not be negative")

        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")

        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= open and close")


@dataclass(frozen=True)
class SignalResult:
    """Represents a normalized analysis signal."""

    symbol: str
    signal: Signal
    confidence: float
    timestamp: datetime
    source: str

    def __post_init__(self):
        """Validate the signal contract."""

        if not self.symbol:
            raise ValueError("symbol must not be empty")

        if self.signal not in ("BUY", "SELL", "HOLD"):
            raise ValueError("signal must be BUY, SELL, or HOLD")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

        if not self.source:
            raise ValueError("source must not be empty")
