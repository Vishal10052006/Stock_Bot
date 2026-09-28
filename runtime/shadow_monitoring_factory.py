"""Factory for the M20 monitoring runtime with optional journal persistence."""

from __future__ import annotations

from monitoring.engine import MonitoringEngine
from monitoring.journal import MonitoringEvent, MonitoringJournal
from monitoring.pipeline import MonitoringPipeline
from monitoring.runtime import MonitoringRuntime
from .shadow_session import ShadowSessionJournal


class _SessionMonitoringJournal(MonitoringJournal):
    """Journal adapter that binds monitoring telemetry to one shadow session."""

    def __init__(self, base: MonitoringJournal, session_id: str) -> None:
        super().__init__(base.path, max_records=base.max_records)
        self._base = base
        self._session_id = session_id

    def append(self, event: MonitoringEvent) -> None:
        if event.correlation_id is None:
            event = MonitoringEvent.create(
                event_type=event.event_type,
                source=event.source,
                payload=event.payload,
                severity=event.severity,
                correlation_id=self._session_id,
                timestamp=event.timestamp,
                schema_version=event.schema_version,
            )
        self._base.append(event)


def build_shadow_monitoring(
    session_journal: ShadowSessionJournal | None,
) -> MonitoringRuntime:
    """Build monitoring with optional session-correlated journal persistence."""
    if session_journal is None:
        return MonitoringRuntime()

    journal = _SessionMonitoringJournal(
        session_journal.journal,
        session_journal.session_id,
    )
    engine = MonitoringEngine(journal=journal)
    pipeline = MonitoringPipeline(engine=engine)
    return MonitoringRuntime(pipeline=pipeline)
