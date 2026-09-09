"""Point-in-time exchange-symbol history for historical securities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class InstrumentSymbolInterval:
    """One point-in-time symbol interval for a stable security identity."""

    isin: str
    symbol: str
    effective_from: date
    exchange: str = "NSE"
    effective_to: date | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the symbol interval."""
        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("exchange must be a non-empty string")

        if not isinstance(self.effective_from, date):
            raise TypeError("effective_from must be a date")

        if isinstance(self.effective_from, datetime):
            raise TypeError("effective_from must be a date")

        if self.effective_to is not None:
            if not isinstance(self.effective_to, date):
                raise TypeError("effective_to must be a date")

            if isinstance(self.effective_to, datetime):
                raise TypeError("effective_to must be a date")

            if self.effective_to < self.effective_from:
                raise ValueError(
                    "effective_to must be on or after effective_from"
                )

        object.__setattr__(
            self,
            "isin",
            self.isin.strip().upper(),
        )
        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "exchange",
            self.exchange.strip().upper(),
        )


@dataclass(frozen=True, slots=True)
class InstrumentSymbolTimeline:
    """Chronological, non-overlapping symbol history for one ISIN."""

    intervals: tuple[InstrumentSymbolInterval, ...]

    def __post_init__(self) -> None:
        """Validate the complete symbol timeline."""
        if not isinstance(self.intervals, tuple):
            object.__setattr__(
                self,
                "intervals",
                tuple(self.intervals),
            )

        if not self.intervals:
            raise ValueError(
                "symbol timeline must contain at least one interval"
            )

        isin = self.intervals[0].isin
        exchange = self.intervals[0].exchange

        for interval in self.intervals:
            if interval.isin != isin:
                raise ValueError(
                    "all symbol intervals must use the same ISIN"
                )

            if interval.exchange != exchange:
                raise ValueError(
                    "all symbol intervals must use the same exchange"
                )

        ordered = tuple(
            sorted(
                self.intervals,
                key=lambda interval: interval.effective_from,
            )
        )

        for index, interval in enumerate(ordered):
            if (
                interval.effective_to is None
                and index != len(ordered) - 1
            ):
                raise ValueError(
                    "open-ended symbol interval must be the final interval"
                )

        for previous, current in zip(
            ordered,
            ordered[1:],
        ):
            if (
                previous.effective_to is not None
                and current.effective_from <= previous.effective_to
            ):
                raise ValueError(
                    "symbol intervals must not overlap"
                )

        object.__setattr__(self, "intervals", ordered)

    @property
    def isin(self) -> str:
        """Return the stable security identity."""
        return self.intervals[0].isin

    @property
    def exchange(self) -> str:
        """Return the exchange for the symbol history."""
        return self.intervals[0].exchange

    def symbol_on(self, target_date: date) -> str | None:
        """Return the exchange symbol applicable on a date."""
        if not isinstance(target_date, date):
            raise TypeError("target_date must be a date")

        if isinstance(target_date, datetime):
            raise TypeError("target_date must be a date")

        for interval in self.intervals:
            if target_date < interval.effective_from:
                return None

            if (
                interval.effective_to is None
                or target_date <= interval.effective_to
            ):
                return interval.symbol

        return None
