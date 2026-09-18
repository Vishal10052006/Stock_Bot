"""Contracts for point-in-time sector classification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class SectorMapping:
    """Point-in-time mapping from an equity symbol to a sector index.

    ``effective_to`` is inclusive. An open-ended mapping remains valid until
    replaced by a later mapping for the same symbol.
    """

    symbol: str
    sector_index_symbol: str
    effective_from: date
    effective_to: date | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if (
            not isinstance(self.sector_index_symbol, str)
            or not self.sector_index_symbol.strip()
        ):
            raise ValueError("sector_index_symbol must be a non-empty string")
        if not isinstance(self.effective_from, date):
            raise TypeError("effective_from must be a date")
        if isinstance(self.effective_from, __import__("datetime").datetime):
            raise TypeError("effective_from must be a date")
        if self.effective_to is not None:
            if not isinstance(self.effective_to, date):
                raise TypeError("effective_to must be a date")
            if isinstance(self.effective_to, __import__("datetime").datetime):
                raise TypeError("effective_to must be a date")
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to must be >= effective_from")

        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(
            self,
            "sector_index_symbol",
            self.sector_index_symbol.strip().upper(),
        )


def validate_sector_mappings(mappings: tuple[SectorMapping, ...]) -> None:
    """Reject overlapping or non-chronological symbol mappings."""
    if not isinstance(mappings, tuple):
        raise TypeError("mappings must be a tuple")
    if not mappings:
        raise ValueError("mappings must not be empty")

    grouped: dict[str, list[SectorMapping]] = {}
    for mapping in mappings:
        if not isinstance(mapping, SectorMapping):
            raise TypeError("mappings must contain SectorMapping values")
        grouped.setdefault(mapping.symbol, []).append(mapping)

    for symbol, values in grouped.items():
        ordered = sorted(values, key=lambda item: item.effective_from)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.effective_to is None:
                raise ValueError(
                    f"open-ended sector mapping for {symbol} cannot precede another mapping"
                )
            if current.effective_from <= previous.effective_to:
                raise ValueError(
                    f"sector mappings overlap for {symbol}"
                )
