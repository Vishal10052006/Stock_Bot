"""Canonical OHLCV candle contract for the trading system.

A Candle represents one completed or in-progress time bucket of market data.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 2 / Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True, slots=True)
class Candle:
    """Immutable OHLCV candle."""

    symbol: str
    exchange: str
    timeframe_minutes: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        """Validate the canonical candle contract."""
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")

        if self.timeframe_minutes <= 0:
            raise ValueError(
                "timeframe_minutes must be greater than zero"
            )

        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        prices = {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }

        for name, value in prices.items():
            if not isfinite(value) or value <= 0:
                raise ValueError(
                    f"{name} must be finite and greater than zero"
                )

        if self.high < max(self.open, self.close):
            raise ValueError(
                "high must be greater than or equal to open and close"
            )

        if self.low > min(self.open, self.close):
            raise ValueError(
                "low must be less than or equal to open and close"
            )

        if self.low > self.high:
            raise ValueError(
                "low must be less than or equal to high"
            )

        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError(
                "volume must be finite and non-negative"
            )
