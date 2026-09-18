"""Immutable history of dated NSE Security Master observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from market.data.historical.nse_security_master_evidence_snapshot import (
    NSESecurityMasterEvidenceSnapshot,
)
from market.data.historical.nse_security_master_observation import (
    NSESecurityMasterObservation,
)


@dataclass(frozen=True, slots=True)
class NSESecurityMasterObservationHistory:
    """Chronological collection of dated NSE Security Master snapshots.

    The history preserves observation dates exactly as published by the
    Security Master snapshots. It does not infer economic or legal
    effective dates from snapshot presence.
    """

    snapshots: tuple[NSESecurityMasterEvidenceSnapshot, ...]

    def __post_init__(self) -> None:
        """Validate and deterministically order the snapshot history."""

        if not isinstance(self.snapshots, tuple):
            object.__setattr__(
                self,
                "snapshots",
                tuple(self.snapshots),
            )

        if not self.snapshots:
            raise ValueError(
                "Security Master observation history must contain "
                "at least one snapshot"
            )

        for index, snapshot in enumerate(self.snapshots):
            if not isinstance(
                snapshot,
                NSESecurityMasterEvidenceSnapshot,
            ):
                raise TypeError(
                    f"snapshots[{index}] must be an "
                    "NSESecurityMasterEvidenceSnapshot"
                )

        snapshot_dates = [
            snapshot.snapshot_date
            for snapshot in self.snapshots
        ]

        if len(snapshot_dates) != len(set(snapshot_dates)):
            raise ValueError(
                "snapshot dates must be unique within observation history"
            )

        ordered = tuple(
            sorted(
                self.snapshots,
                key=lambda snapshot: snapshot.snapshot_date,
            )
        )

        object.__setattr__(self, "snapshots", ordered)

    @property
    def start_date(self) -> date:
        """Return the earliest observation date."""

        return self.snapshots[0].snapshot_date

    @property
    def end_date(self) -> date:
        """Return the latest observation date."""

        return self.snapshots[-1].snapshot_date

    def observations(
        self,
    ) -> tuple[NSESecurityMasterObservation, ...]:
        """Flatten all snapshots into chronological identity observations."""

        observations: list[NSESecurityMasterObservation] = []

        for snapshot in self.snapshots:
            observations.extend(snapshot.observations())

        return tuple(observations)

    def observations_for(
        self,
        symbol: str,
        series: str = "EQ",
    ) -> tuple[NSESecurityMasterObservation, ...]:
        """Return observations for one symbol and series in chronological order."""

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

        return tuple(
            observation
            for observation in self.observations()
            if (
                observation.symbol == normalized_symbol
                and observation.series == normalized_series
            )
        )
