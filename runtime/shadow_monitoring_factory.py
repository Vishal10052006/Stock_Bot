"""Factory for the M20 monitoring runtime with optional journal persistence."""

from __future__ import annotations

from monitoring.engine import MonitoringEngine
from monitoring.pipeline import MonitoringPipeline
from monitoring.runtime import MonitoringRuntime
from .shadow_session import ShadowSessionJournal


def build_shadow_monitoring(
    session_journal: ShadowSessionJournal | None,
) -> MonitoringRuntime:
    """Build monitoring with the shadow session journal when enabled."""
    if session_journal is None:
        return MonitoringRuntime()

    engine = MonitoringEngine(journal=session_journal.journal)
    pipeline = MonitoringPipeline(engine=engine)
    return MonitoringRuntime(pipeline=pipeline)
