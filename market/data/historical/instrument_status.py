"""Instrument lifecycle/status contracts for historical market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class InstrumentStatusType(str, Enum):
    """Lifecycle states that affect instrument data eligibility."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELISTED = "delisted"


@dataclass(frozen=True, slots=True)
class InstrumentStatus:
    """Status interval for one instrument."""

    symbol: str
    status: InstrumentStatusType
    effective_from: date
    effective_to: date | None = None

    def __post_init__(self) -> None:
        """Validate the instrument status contract."""
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.status, InstrumentStatusType):
            raise TypeError("status must be an InstrumentStatusType")

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
            "symbol",
            self.symbol.strip().upper(),
        )


@dataclass(frozen=True, slots=True)
class InstrumentStatusTimeline:
    """Ordered, non-overlapping lifecycle intervals for one instrument."""

    statuses: tuple[InstrumentStatus, ...]

    def __post_init__(self) -> None:
        """Validate the complete status timeline."""
        if not isinstance(self.statuses, tuple):
            object.__setattr__(
                self,
                "statuses",
                tuple(self.statuses),
            )

        if not self.statuses:
            raise ValueError(
                "status timeline must contain at least one status"
            )

        symbol = self.statuses[0].symbol

        for status in self.statuses:
            if status.symbol != symbol:
                raise ValueError(
                    "all status intervals must use the same symbol"
                )

        ordered = tuple(
            sorted(
                self.statuses,
                key=lambda status: status.effective_from,
            )
        )

        for index, status in enumerate(ordered):
            if (
                status.effective_to is None
                and index != len(ordered) - 1
            ):
                raise ValueError(
                    "open-ended instrument status must be the final interval"
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
                    "instrument status intervals must not overlap"
                )

        object.__setattr__(self, "statuses", ordered)

    @property
    def symbol(self) -> str:
        """Return the instrument symbol represented by the timeline."""
        return self.statuses[0].symbol

    def status_on(
        self,
        target_date: date,
    ) -> InstrumentStatusType | None:
        """Return the status applicable on a date, if known."""
        if not isinstance(target_date, date):
            raise TypeError("target_date must be a date")

        if isinstance(target_date, datetime):
            raise TypeError("target_date must be a date")

        for status in self.statuses:
            if target_date < status.effective_from:
                return None

            if (
                status.effective_to is None
                or target_date <= status.effective_to
            ):
                return status.status

        return None
