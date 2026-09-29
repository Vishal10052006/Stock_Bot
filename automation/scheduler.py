"""Cooperative scheduling primitives for local automation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    """Named interval schedule."""

    name: str
    interval_seconds: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("schedule name must not be empty")
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")


class Scheduler:
    """Job registry without hidden threads or trading authority."""

    def __init__(self) -> None:
        self._jobs: list[tuple[ScheduleSpec, Callable[[], None]]] = []

    def register(self, spec: ScheduleSpec, job: Callable[[], None]) -> None:
        """Register a callable job."""
        self._jobs.append((spec, job))

    def jobs(self) -> tuple[tuple[ScheduleSpec, Callable[[], None]], ...]:
        """Return registered jobs."""
        return tuple(self._jobs)

    @staticmethod
    def next_five_minute_boundary(timestamp: datetime) -> datetime:
        """Return the next UTC five-minute boundary."""
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        ts = timestamp.astimezone(timezone.utc).replace(second=0, microsecond=0)
        minute = ((ts.minute // 5) + 1) * 5
        if minute >= 60:
            ts += timedelta(hours=1)
            minute = 0
        return ts.replace(minute=minute)
