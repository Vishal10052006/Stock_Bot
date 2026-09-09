"""Immutable dated NSE Security Master evidence snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from market.data.historical.nse_security_master_evidence import (
    NSESecurityMasterEvidence,
)
from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)


@dataclass(frozen=True, slots=True)
class NSESecurityMasterEvidenceSnapshot:
    """One dated NSE Security Master snapshot with complete evidence."""

    snapshot_date: date
    evidence: tuple[NSESecurityMasterEvidence, ...]

    def __post_init__(self) -> None:
        """Validate the dated Security Master evidence collection."""

        if not isinstance(self.snapshot_date, date):
            raise TypeError("snapshot_date must be a date")

        if isinstance(self.snapshot_date, datetime):
            raise TypeError("snapshot_date must be a date")

        if not isinstance(self.evidence, tuple):
            object.__setattr__(
                self,
                "evidence",
                tuple(self.evidence),
            )

        if not self.evidence:
            raise ValueError(
                "Security Master evidence snapshot must contain "
                "at least one evidence record"
            )

        for index, item in enumerate(self.evidence):
            if not isinstance(item, NSESecurityMasterEvidence):
                raise TypeError(
                    f"evidence[{index}] must be an "
                    "NSESecurityMasterEvidence"
                )

            if item.identity.snapshot_date != self.snapshot_date:
                raise ValueError(
                    "all Security Master evidence must use the "
                    "snapshot date"
                )

        fin_instrm_ids = [
            item.identity.fin_instrm_id
            for item in self.evidence
        ]

        if len(fin_instrm_ids) != len(set(fin_instrm_ids)):
            raise ValueError(
                "FinInstrmId must be unique within a "
                "Security Master evidence snapshot"
            )

        symbol_series = [
            (
                item.identity.symbol,
                item.identity.series,
            )
            for item in self.evidence
        ]

        if len(symbol_series) != len(set(symbol_series)):
            raise ValueError(
                "(symbol, series) must be unique within a "
                "Security Master evidence snapshot"
            )

        ordered = tuple(
            sorted(
                self.evidence,
                key=lambda item: (
                    item.identity.symbol,
                    item.identity.series,
                    item.identity.fin_instrm_id,
                ),
            )
        )

        object.__setattr__(self, "evidence", ordered)

    def observations(
        self,
    ) -> tuple[NSESecurityMasterObservation, ...]:
        """Return identity-only observations from this evidence snapshot.

        This conversion intentionally discards lifecycle information and
        must only be used when an identity-observation contract is required.
        """

        return tuple(
            NSESecurityMasterObservation.from_record(
                item.identity
            )
            for item in self.evidence
        )

    def evidence_for(
        self,
        symbol: str,
        series: str = "EQ",
    ) -> NSESecurityMasterEvidence | None:
        """Return complete evidence for a symbol and series."""

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

        for item in self.evidence:
            if (
                item.identity.symbol == normalized_symbol
                and item.identity.series == normalized_series
            ):
                return item

        return None

    def evidence_by_fin_instrm_id(
        self,
        fin_instrm_id: str,
    ) -> NSESecurityMasterEvidence | None:
        """Return complete evidence by NSE financial-instrument ID."""

        if not isinstance(fin_instrm_id, str):
            raise TypeError("fin_instrm_id must be a string")

        normalized = fin_instrm_id.strip()

        if not normalized:
            raise ValueError("fin_instrm_id must not be empty")

        for item in self.evidence:
            if item.identity.fin_instrm_id == normalized:
                return item

        return None
