"""Immutable dated NSE Security Master snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from market.data.historical.nse_security_master import (
    NSESecurityMasterRecord,
)
from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)


@dataclass(frozen=True, slots=True)
class NSESecurityMasterSnapshot:
    """One dated NSE Security Master snapshot.

    The snapshot groups the exact instrument records observed on one NSE
    Security Master date. ISIN is deliberately not required to be unique:
    NSE can expose multiple instrument records sharing an ISIN.
    """

    snapshot_date: date
    records: tuple[NSESecurityMasterRecord, ...]

    def __post_init__(self) -> None:
        """Validate the dated Security Master collection."""

        if not isinstance(self.snapshot_date, date):
            raise TypeError("snapshot_date must be a date")

        if isinstance(self.snapshot_date, datetime):
            raise TypeError("snapshot_date must be a date")

        if not isinstance(self.records, tuple):
            object.__setattr__(
                self,
                "records",
                tuple(self.records),
            )

        if not self.records:
            raise ValueError(
                "Security Master snapshot must contain at least one record"
            )

        for index, record in enumerate(self.records):
            if not isinstance(record, NSESecurityMasterRecord):
                raise TypeError(
                    f"records[{index}] must be an NSESecurityMasterRecord"
                )

            if record.snapshot_date != self.snapshot_date:
                raise ValueError(
                    "all Security Master records must use the "
                    "snapshot date"
                )

        fin_instrm_ids = [
            record.fin_instrm_id
            for record in self.records
        ]

        if len(fin_instrm_ids) != len(set(fin_instrm_ids)):
            raise ValueError(
                "FinInstrmId must be unique within a Security Master snapshot"
            )

        symbol_series = [
            (record.symbol, record.series)
            for record in self.records
        ]

        if len(symbol_series) != len(set(symbol_series)):
            raise ValueError(
                "(symbol, series) must be unique within a "
                "Security Master snapshot"
            )

        ordered = tuple(
            sorted(
                self.records,
                key=lambda record: (
                    record.symbol,
                    record.series,
                    record.fin_instrm_id,
                ),
            )
        )

        object.__setattr__(self, "records", ordered)


    def observations(self) -> tuple[NSESecurityMasterObservation, ...]:
        """Return dated observations for every record in this snapshot.

        The snapshot date becomes ``observed_on``. This conversion does not
        infer an instrument's effective date or establish security lineage.
        """

        return tuple(
            NSESecurityMasterObservation.from_record(record)
            for record in self.records
        )

    def record_for(
        self,
        symbol: str,
        series: str = "EQ",
    ) -> NSESecurityMasterRecord | None:
        """Return the dated record for a symbol and series."""

        if not isinstance(symbol, str):
            raise TypeError("symbol must be a string")

        if not isinstance(series, str):
            raise TypeError("series must be a string")

        normalized_symbol = symbol.strip().upper()
        normalized_series = series.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol must not be empty")

        if not normalized_series:
            raise ValueError("series must not be empty")

        for record in self.records:
            if (
                record.symbol == normalized_symbol
                and record.series == normalized_series
            ):
                return record

        return None

    def record_by_fin_instrm_id(
        self,
        fin_instrm_id: str,
    ) -> NSESecurityMasterRecord | None:
        """Return a dated record by NSE financial-instrument ID."""

        if not isinstance(fin_instrm_id, str):
            raise TypeError("fin_instrm_id must be a string")

        normalized = fin_instrm_id.strip()

        if not normalized:
            raise ValueError("fin_instrm_id must not be empty")

        for record in self.records:
            if record.fin_instrm_id == normalized:
                return record

        return None
