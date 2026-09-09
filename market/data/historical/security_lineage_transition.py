"""Verified security-lineage transition evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from market.data.historical.nse_symbol_change import (
    NSESymbolChangeRecord,
)


@dataclass(frozen=True, slots=True)
class SecurityLineageTransition:
    """One verified identity transition supported by explicit evidence.

    This contract represents the transition evidence itself. It deliberately
    does not claim which NSE instrument record or ISIN existed before or after
    the transition. Those facts must be corroborated separately from dated
    Security Master observations.
    """

    old_symbol: str
    new_symbol: str
    effective_date: date
    source: str


    @classmethod
    def from_nse_symbol_change(
        cls,
        record: NSESymbolChangeRecord,
    ) -> "SecurityLineageTransition":
        """Convert explicit NSE symbol-change evidence."""

        if not isinstance(record, NSESymbolChangeRecord):
            raise TypeError(
                "record must be an NSESymbolChangeRecord"
            )

        return cls(
            old_symbol=record.old_symbol,
            new_symbol=record.new_symbol,
            effective_date=record.effective_date,
            source=record.source,
        )

    def __post_init__(self) -> None:
        """Validate and normalize transition evidence."""

        for name, value in (
            ("old_symbol", self.old_symbol),
            ("new_symbol", self.new_symbol),
            ("source", self.source),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{name} must be a non-empty string"
                )

        if not isinstance(self.effective_date, date):
            raise TypeError("effective_date must be a date")

        if isinstance(self.effective_date, datetime):
            raise TypeError("effective_date must be a date")

        object.__setattr__(
            self,
            "old_symbol",
            self.old_symbol.strip().upper(),
        )
        normalized_old_symbol = self.old_symbol.strip().upper()
        normalized_new_symbol = self.new_symbol.strip().upper()

        if normalized_old_symbol == normalized_new_symbol:
            raise ValueError(
                "old_symbol and new_symbol must differ for a "
                "security-lineage transition"
            )

        object.__setattr__(
            self,
            "old_symbol",
            normalized_old_symbol,
        )
        object.__setattr__(
            self,
            "new_symbol",
            normalized_new_symbol,
        )
        object.__setattr__(
            self,
            "source",
            self.source.strip(),
        )
