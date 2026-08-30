"""
Stock Bot — Core Data Models

Defines immutable domain objects shared across the
market-data, signal, strategy, risk, and trading layers.
"""

from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from math import isfinite
from typing import Literal


Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass(frozen=True)
class MarketBar:
    """Represents one validated OHLCV market-data bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        """Validate the complete OHLCV domain contract."""

        # A market bar must identify a real, non-blank instrument.
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        # Timestamps must be explicit about their timezone. The concrete
        # market timezone is handled by normalization, not by this model.
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        # OHLCV fields must be real numeric values. bool is deliberately
        # rejected because True/False are subclasses of int in Python.
        numeric_fields = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

        for field_name, value in numeric_fields.items():
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{field_name} must be a real number")

            if not isfinite(value):
                raise ValueError(f"{field_name} must be finite")

        # OHLC prices must be strictly positive; zero/negative prices are
        # invalid market observations.
        if (
            self.open <= 0
            or self.high <= 0
            or self.low <= 0
            or self.close <= 0
        ):
            raise ValueError("OHLC prices must be greater than zero")

        # Volume may legitimately be zero, but never negative.
        if self.volume < 0:
            raise ValueError("volume must not be negative")

        # The candle's high must contain both open and close.
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= open and close")

        # The candle's low must contain both open and close.
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
