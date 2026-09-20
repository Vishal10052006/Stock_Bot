"""Point-in-time sector membership resolution.

Sector membership is external research data. This module resolves only
explicit SectorMapping records; it never infers a sector from a company's
current classification or fills historical gaps.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from market.data.context.models import SectorMapping, validate_sector_mappings
from market.data.context.sector_registry import sector_context_priority


@dataclass(frozen=True, slots=True)
class SectorMembershipResolution:
    """Resolved PIT sector membership for one symbol on one date."""

    symbol: str
    as_of: date
    sector_index_symbol: str | None


class PointInTimeSectorMembershipProvider:
    """Resolve explicit historical stock-to-sector-index mappings.

    The provider is deliberately data-only. Callers must supply authoritative
    dated mappings. No current membership is applied backward in time.
    """

    def __init__(self, mappings: Sequence[SectorMapping]) -> None:
        normalized = tuple(mappings)
        validate_sector_mappings(normalized)
        self._mappings = normalized

    @property
    def mappings(self) -> tuple[SectorMapping, ...]:
        """Return the immutable mapping set."""
        return self._mappings

    def resolve(
        self,
        *,
        symbol: str,
        as_of: date,
    ) -> SectorMembershipResolution:
        """Resolve one symbol's sector index at an exchange-local date."""
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("symbol must be a non-empty string")
        if not isinstance(as_of, date):
            raise TypeError("as_of must be a date")

        normalized_symbol = symbol.strip().upper()
        matches = [
            mapping
            for mapping in self._mappings
            if mapping.symbol == normalized_symbol
            and mapping.effective_from <= as_of
            and (
                mapping.effective_to is None
                or as_of <= mapping.effective_to
            )
        ]

        if matches:
            # Multiple simultaneous sector memberships are valid. The
            # existing feature schema has one sector_* family, so reduce
            # them using the explicit, deterministic model-side policy.
            selected = min(
                matches,
                key=lambda mapping: (
                    sector_context_priority(mapping.sector_index_symbol),
                    -mapping.effective_from.toordinal(),
                    mapping.sector_index_symbol,
                ),
            )
            sector_index_symbol = selected.sector_index_symbol
        else:
            sector_index_symbol = None
        return SectorMembershipResolution(
            symbol=normalized_symbol,
            as_of=as_of,
            sector_index_symbol=sector_index_symbol,
        )

    def resolve_many(
        self,
        *,
        symbols: Iterable[str],
        as_of: date,
        require_complete: bool = True,
    ) -> tuple[SectorMembershipResolution, ...]:
        """Resolve multiple symbols deterministically for one PIT date.

        With require_complete=True, an unmapped symbol raises instead of
        silently producing missing sector features.
        """
        if not isinstance(as_of, date):
            raise TypeError("as_of must be a date")

        normalized = tuple(
            symbol.strip().upper()
            if isinstance(symbol, str)
            else symbol
            for symbol in symbols
        )

        if any(
            not isinstance(symbol, str) or not symbol
            for symbol in normalized
        ):
            raise ValueError("symbols must contain non-empty strings")

        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must be unique")

        resolutions = tuple(
            self.resolve(symbol=symbol, as_of=as_of)
            for symbol in sorted(normalized)
        )

        if require_complete:
            missing = tuple(
                resolution.symbol
                for resolution in resolutions
                if resolution.sector_index_symbol is None
            )
            if missing:
                raise ValueError(
                    "missing point-in-time sector membership for "
                    f"{as_of.isoformat()}: {list(missing)}"
                )

        return resolutions

    def mappings_for(
        self,
        *,
        symbols: Iterable[str],
        as_of: date,
        require_complete: bool = True,
    ) -> tuple[SectorMapping, ...]:
        """Return explicit mappings valid for symbols on as_of."""
        resolutions = self.resolve_many(
            symbols=symbols,
            as_of=as_of,
            require_complete=require_complete,
        )

        result: list[SectorMapping] = []
        for resolution in resolutions:
            if resolution.sector_index_symbol is None:
                continue

            mapping = next(
                mapping
                for mapping in self._mappings
                if mapping.symbol == resolution.symbol
                and mapping.effective_from <= as_of
                and (
                    mapping.effective_to is None
                    or as_of <= mapping.effective_to
                )
            )
            result.append(mapping)

        return tuple(result)
