"""NSE dated security-master identity contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class NSESecurityMasterRecord:
    """Identity fields for one NSE Security Master record.

    ``fin_instrm_id`` identifies the specific NSE financial-instrument
    record in a dated Security Master snapshot.

    ``symbol`` is the NSE ticker represented by that record.
    ``series`` identifies the NSE security series, such as ``EQ``.
    ``isin`` is a security/linkage attribute and is not assumed to be
    unique across NSE instrument records.
    ``exchange`` identifies the listing venue.
    """

    snapshot_date: date
    fin_instrm_id: str
    symbol: str
    series: str
    isin: str
    exchange: str = "NSE"

    def __post_init__(self) -> None:
        """Validate and normalize the Security Master identity."""
        if not isinstance(self.snapshot_date, date):
            raise TypeError("snapshot_date must be a date")

        if isinstance(self.snapshot_date, datetime):
            raise TypeError("snapshot_date must be a date")

        if (
            not isinstance(self.fin_instrm_id, str)
            or not self.fin_instrm_id.strip()
        ):
            raise ValueError(
                "fin_instrm_id must be a non-empty string"
            )

        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.series, str) or not self.series.strip():
            raise ValueError("series must be a non-empty string")

        if not isinstance(self.isin, str) or not self.isin.strip():
            raise ValueError("isin must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange.strip():
            raise ValueError("exchange must be a non-empty string")

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
