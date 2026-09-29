"""Thread-safe automation run state and idempotency store."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from .contracts import RunContext, StageEvent


@dataclass(slots=True)
class RunRecord:
    """Mutable internal state behind immutable public contracts."""

    context: RunContext
    events: list[StageEvent]


class RunStateStore:
    """Process-local persistence seam for automated runs."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._runs: dict[str, RunRecord] = {}
        self._idempotency: dict[str, str] = {}

    def create(self, context: RunContext) -> RunRecord:
        """Register a run, returning an existing logical run when duplicated."""
        with self._lock:
            existing = self._idempotency.get(context.idempotency_key)
            if existing is not None:
                return self._runs[existing]
            record = RunRecord(context=context, events=[])
            self._runs[context.run_id] = record
            self._idempotency[context.idempotency_key] = context.run_id
            return record

    def update_context(self, context: RunContext) -> None:
        """Update a known run."""
        with self._lock:
            record = self._runs.get(context.run_id)
            if record is None:
                raise KeyError(f"unknown run_id: {context.run_id}")
            record.context = context

    def append(self, event: StageEvent) -> None:
        """Append an event to an existing run."""
        with self._lock:
            record = self._runs.get(event.run_id)
            if record is None:
                raise KeyError(f"unknown run_id: {event.run_id}")
            record.events.append(event)
