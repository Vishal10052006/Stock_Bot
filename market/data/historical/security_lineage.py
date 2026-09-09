"""Verified point-in-time security lineage contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SecurityLineageObservation:
    """One dated NSE instrument record belonging to a verified lineage."""

    fin_instrm_id: str
    symbol: str
    series: str
    isin: str
    exchange: str
    effective_from: date
    effective_to: date | None = None
    source: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize one lineage observation."""
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

        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

        for name in (
            "fin_instrm_id",
            "symbol",
            "series",
            "isin",
            "exchange",
        ):
            object.__setattr__(
                self,
                name,
                getattr(self, name).strip().upper(),
            )

        object.__setattr__(self, "source", self.source.strip())


@dataclass(frozen=True, slots=True)
class SecurityLineage:
    """Verified chronological lineage for one exchange security."""

    lineage_id: str
    observations: tuple[SecurityLineageObservation, ...]

    def __post_init__(self) -> None:
        """Validate the complete lineage."""
        if not isinstance(self.lineage_id, str) or not self.lineage_id.strip():
            raise ValueError("lineage_id must be a non-empty string")

        if not isinstance(self.observations, tuple):
            object.__setattr__(
                self,
                "observations",
                tuple(self.observations),
            )

        if not self.observations:
            raise ValueError(
                "security lineage must contain at least one observation"
            )

        for index, observation in enumerate(self.observations):
            if not isinstance(observation, SecurityLineageObservation):
                raise TypeError(
                    f"observations[{index}] must be a "
                    "SecurityLineageObservation"
                )

        exchange = self.observations[0].exchange

        for observation in self.observations:
            if observation.exchange != exchange:
                raise ValueError(
                    "all lineage observations must use the same exchange"
                )

        ordered = tuple(
            sorted(
                self.observations,
                key=lambda observation: observation.effective_from,
            )
        )

        for index, observation in enumerate(ordered):
            if (
                observation.effective_to is None
                and index != len(ordered) - 1
            ):
                raise ValueError(
                    "open-ended lineage observation must be the final "
                    "observation"
                )

        for previous, current in zip(ordered, ordered[1:]):
            if (
                previous.effective_to is not None
                and current.effective_from <= previous.effective_to
            ):
                raise ValueError(
                    "security lineage observations must not overlap"
                )

        object.__setattr__(
            self,
            "lineage_id",
            self.lineage_id.strip(),
        )
        object.__setattr__(self, "observations", ordered)

    @property
    def exchange(self) -> str:
        """Return the exchange represented by this lineage."""
        return self.observations[0].exchange

    def observation_on(
        self,
        target_date: date,
    ) -> SecurityLineageObservation | None:
        """Return the verified instrument record applicable on a date."""
        if not isinstance(target_date, date):
            raise TypeError("target_date must be a date")

        if isinstance(target_date, datetime):
            raise TypeError("target_date must be a date")

        for observation in self.observations:
            if target_date < observation.effective_from:
                return None

            if (
                observation.effective_to is None
                or target_date <= observation.effective_to
            ):
                return observation

        return None
