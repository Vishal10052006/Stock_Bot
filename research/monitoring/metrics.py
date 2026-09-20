"""RB-14 lightweight operational metrics."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ResearchMetrics:
    ingested: int = 0
    rejected: int = 0
    pit_rejected: int = 0
    events: int = 0

    def record_ingest(self, count: int = 1) -> None:
        self.ingested += count

    def record_rejection(self, count: int = 1) -> None:
        self.rejected += count

    def record_pit_rejection(self, count: int = 1) -> None:
        self.pit_rejected += count

    def record_events(self, count: int = 1) -> None:
        self.events += count
