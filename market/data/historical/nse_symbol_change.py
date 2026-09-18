"""NSE historical symbol-change evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class NSESymbolChangeRecord:
    """One NSE-published historical symbol transition."""

    company: str | None
    old_symbol: str
    new_symbol: str
    effective_date: date
    source: str = "nse_symbol_change"

    def __post_init__(self) -> None:
        """Validate and normalize the symbol-change evidence."""

        if self.company is not None and not isinstance(self.company, str):
            raise TypeError("company must be a string or None")

        if self.company is not None and not self.company.strip():
            object.__setattr__(self, "company", None)

        if (
            not isinstance(self.old_symbol, str)
            or not self.old_symbol.strip()
        ):
            raise ValueError("old_symbol must be a non-empty string")

        if (
            not isinstance(self.new_symbol, str)
            or not self.new_symbol.strip()
        ):
            raise ValueError("new_symbol must be a non-empty string")

        if not isinstance(self.effective_date, date):
            raise TypeError("effective_date must be a date")

        if isinstance(self.effective_date, datetime):
            raise TypeError("effective_date must be a date")

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

        if self.company is not None:
            object.__setattr__(
                self,
                "company",
                self.company.strip(),
            )
        object.__setattr__(
            self,
            "old_symbol",
            self.old_symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "new_symbol",
            self.new_symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "source",
            self.source.strip(),
        )
