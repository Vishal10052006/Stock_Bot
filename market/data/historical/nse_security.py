"""NSE security-wise daily market-data contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite


@dataclass(frozen=True, slots=True)
class NSESecurityDailyBar:
    """One NSE security-wise daily price/volume observation."""

    symbol: str
    series: str
    session_date: date

    previous_close: float
    open: float
    high: float
    low: float
    last_traded_price: float
    close: float
    vwap: float

    traded_quantity: int
    traded_value: float
    total_trades: int

    def __post_init__(self) -> None:
        """Validate the NSE daily security record."""

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.series, str) or not self.series.strip():
            raise ValueError("series must be a non-empty string")

        if isinstance(self.session_date, datetime):
            raise TypeError("session_date must be a date")

        if not isinstance(self.session_date, date):
            raise TypeError("session_date must be a date")

        prices = {
            "previous_close": self.previous_close,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "last_traded_price": self.last_traded_price,
            "close": self.close,
            "vwap": self.vwap,
        }

        for name, value in prices.items():
            if not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric")

            if isinstance(value, bool) or not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

            if float(value) <= 0:
                raise ValueError(f"{name} must be greater than zero")

        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")

        if self.high < self.open or self.high < self.close:
            raise ValueError(
                "high must be greater than or equal to open and close"
            )

        if self.low > self.open or self.low > self.close:
            raise ValueError(
                "low must be less than or equal to open and close"
            )

        if not isinstance(self.traded_quantity, int) or isinstance(
            self.traded_quantity,
            bool,
        ):
            raise TypeError("traded_quantity must be an integer")

        if self.traded_quantity < 0:
            raise ValueError("traded_quantity must be non-negative")

        if not isinstance(self.traded_value, (int, float)):
            raise TypeError("traded_value must be numeric")

        if isinstance(self.traded_value, bool) or not isfinite(
            float(self.traded_value)
        ):
            raise ValueError("traded_value must be finite")

        if self.traded_value < 0:
            raise ValueError("traded_value must be non-negative")

        if not isinstance(self.total_trades, int) or isinstance(
            self.total_trades,
            bool,
        ):
            raise TypeError("total_trades must be an integer")

        if self.total_trades < 0:
            raise ValueError("total_trades must be non-negative")

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "series", self.series.strip().upper())
