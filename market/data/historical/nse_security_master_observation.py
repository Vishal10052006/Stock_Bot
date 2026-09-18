"""Dated observations extracted from NSE Security Master snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)


@dataclass(frozen=True, slots=True)
class NSESecurityMasterObservation:
    """One point-in-time observation of an NSE instrument record.

    ``observed_on`` records when NSE published the instrument record in a
    Security Master snapshot. It is deliberately not called
    ``effective_from`` because a snapshot observation does not, by itself,
    prove the instrument's economic/legal effective date.
    """

    observed_on: date
    fin_instrm_id: str
    symbol: str
    series: str
    isin: str
    exchange: str = "NSE"

    def __post_init__(self) -> None:
        """Validate and normalize one dated Security Master observation."""

        if not isinstance(self.observed_on, date):
            raise TypeError("observed_on must be a date")

        if isinstance(self.observed_on, datetime):
            raise TypeError("observed_on must be a date")

        fields = {
            "fin_instrm_id": self.fin_instrm_id,
            "symbol": self.symbol,
            "series": self.series,
            "isin": self.isin,
            "exchange": self.exchange,
        }

        for name, value in fields.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{name} must be a non-empty string"
                )

        object.__setattr__(
            self,
            "fin_instrm_id",
            self.fin_instrm_id.strip(),
        )
        object.__setattr__(
            self,
            "symbol",
            self.symbol.strip().upper(),
        )
        object.__setattr__(
            self,
            "series",
            self.series.strip().upper(),
        )
        object.__setattr__(
            self,
            "isin",
            self.isin.strip().upper(),
        )
        object.__setattr__(
            self,
            "exchange",
            self.exchange.strip().upper(),
        )

    @classmethod
    def from_record(
        cls,
        record: NSESecurityMasterRecord,
    ) -> "NSESecurityMasterObservation":
        """Convert a dated Security Master record into an observation."""

        if not isinstance(record, NSESecurityMasterRecord):
            raise TypeError(
                "record must be an NSESecurityMasterRecord"
            )

        return cls(
            observed_on=record.snapshot_date,
            fin_instrm_id=record.fin_instrm_id,
            symbol=record.symbol,
            series=record.series,
            isin=record.isin,
            exchange=record.exchange,
        )
