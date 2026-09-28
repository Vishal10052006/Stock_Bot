from monitoring.engine import MonitoringEngine
from monitoring.health import ComponentHealth, HealthStatus
from monitoring.journal import MonitoringJournal
from monitoring.alerts import AlertSeverity


def test_engine_persists_health_metric_and_alert_events(tmp_path) -> None:
    journal = MonitoringJournal(tmp_path / "monitoring.jsonl")
    engine = MonitoringEngine(journal=journal)

    engine.record_health(
        ComponentHealth(
            component="market_bot",
            status=HealthStatus.HEALTHY,
            observed_at="2026-09-24T14:00:00+00:00",
        )
    )
    engine.record_metric(
        "system.error_rate",
        0.01,
        timestamp="2026-09-24T14:00:01+00:00",
    )
    engine.emit_alert(
        code="TEST_ALERT",
        severity=AlertSeverity.WARNING,
        message="test",
        component="system",
        timestamp="2026-09-24T14:00:02+00:00",
    )

    events = journal.events()

    assert [event.event_type for event in events] == [
        "HEALTH",
        "METRIC",
        "ALERT",
    ]
    assert events[1].payload["value"] == 0.01


def test_engine_without_journal_keeps_observability_in_memory() -> None:
    engine = MonitoringEngine()

    engine.record_metric("test.metric", 1.0)

    assert engine.snapshot().metrics["test.metric"] == 1.0
