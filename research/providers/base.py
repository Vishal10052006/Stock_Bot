"""Provider contracts; provider-specific code stops at this boundary."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from research.contracts import ResearchDocument


class ResearchProvider(Protocol):
    source_id: str

    def fetch(
        self,
        *,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
    ) -> Sequence[ResearchDocument]:
        """Fetch raw/normalized documents without creating trading signals."""
        ...


class StaticResearchProvider:
    """Deterministic provider used by tests and offline research."""

    def __init__(self, source_id: str, documents: Sequence[ResearchDocument]) -> None:
        self.source_id = source_id
        self._documents = tuple(documents)

    def fetch(self, *, symbols: Sequence[str], start: datetime, end: datetime) -> Sequence[ResearchDocument]:
        symbol_set = set(symbols)
        return tuple(
            d for d in self._documents
            if d.available_at <= end and d.available_at >= start
            and (not symbol_set or symbol_set.intersection(d.symbols))
        )
