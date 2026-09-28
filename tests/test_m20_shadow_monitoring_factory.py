"""Tests for persistent M20 monitoring construction."""

from monitoring.runtime import MonitoringRuntime
from runtime.shadow_monitoring_factory import build_shadow_monitoring
from runtime.shadow_session import ShadowSessionJournal
from market.data.metrics import DataQualityMetrics


def test_factory_without_journal_is_observational() -> None:
    runtime = build_shadow_monitoring(None)
    assert isinstance(runtime, MonitoringRuntime)
    runtime.observe_data_quality(DataQualityMetrics().snapshot())


def test_factory_persists_monitoring_events(tmp_path) -> None:
    session = ShadowSessionJournal.open(
        tmp_path / "m20.jsonl",
        session_id="monitoring-test",
    )
    runtime = build_shadow_monitoring(session)

    runtime.observe_data_quality(DataQualityMetrics().snapshot())

    events = session.events()
    assert events
    assert any(event.event_type == "METRIC" for event in events)
