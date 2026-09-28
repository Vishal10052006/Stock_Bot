from monitoring.engine import MonitoringEngine
from monitoring.metrics import MetricsCollector


def test_metrics_collector_tracks_latest_values_without_scanning_history() -> None:
    collector = MetricsCollector(max_samples=3)
    collector.record("risk.value", 1.0)
    collector.record("risk.value", 2.0)
    collector.record("execution.value", 3.0)

    assert collector.latest_values() == {
        "risk.value": 2.0,
        "execution.value": 3.0,
    }
    assert collector.latest("risk.value").value == 2.0  # type: ignore[union-attr]


def test_metrics_collector_rebuilds_latest_values_after_bounded_eviction() -> None:
    collector = MetricsCollector(max_samples=3)
    collector.record("old.metric", 1.0)
    collector.record("risk.value", 2.0)
    collector.record("execution.value", 3.0)
    collector.record("new.metric", 4.0)

    assert len(collector.snapshot()) == 3
    assert collector.latest_values() == {
        "risk.value": 2.0,
        "execution.value": 3.0,
        "new.metric": 4.0,
    }


def test_monitoring_engine_snapshot_uses_latest_metric_values() -> None:
    engine = MonitoringEngine(metrics=MetricsCollector(max_samples=10))
    engine.record_metric("risk.value", 1.0)
    engine.record_metric("risk.value", 2.0)

    snapshot = engine.snapshot()

    assert snapshot.metrics == {"risk.value": 2.0}
