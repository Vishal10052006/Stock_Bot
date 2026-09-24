from datetime import datetime, timezone

from monitoring import (
    AlertSeverity,
    ComponentHealth,
    MonitoringEngine,
    MonitoringPolicy,
    MonitoringSnapshot,
    MonitoringStore,
)


def test_monitoring_snapshot_emits_cross_domain_alerts(tmp_path):
    engine = MonitoringEngine(
        policy=MonitoringPolicy(
            max_data_freshness_seconds=10.0,
            max_feed_latency_ms=100.0,
            max_prediction_psi=0.20,
        ),
        store=MonitoringStore(tmp_path / "monitoring.jsonl"),
    )
    snapshot = MonitoringSnapshot(
        timestamp=datetime.now(timezone.utc),
        data_freshness_seconds=25.0,
        missing_candles=1,
        duplicate_events=1,
        feed_latency_ms=250.0,
        feature_missing_rate=0.10,
        error_rate=0.20,
        stale_rate=0.30,
        prediction_psi=0.50,
        drawdown_pct=2.0,
        gross_exposure_pct=80.0,
        execution_latency_ms=2500.0,
        slippage_bps=75.0,
        order_rejection_rate=0.10,
        reconciliation_mismatch=True,
    )

    alerts = engine.inspect_snapshot(snapshot)

    codes = {alert.code for alert in alerts}
    assert "DATA_STALE" in codes
    assert "MISSING_CANDLES" in codes
    assert "DUPLICATE_EVENTS" in codes
    assert "PREDICTION_DRIFT" in codes
    assert "POSITION_RECONCILIATION_MISMATCH" in codes


def test_health_aggregates_component_failure(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    health = engine.build_health(
        {
            "market_feed": ComponentHealth.HEALTHY,
            "prediction": ComponentHealth.FAILED,
            "execution": ComponentHealth.HEALTHY,
        }
    )
    assert health.overall is ComponentHealth.FAILED


def test_monitoring_persists_events_and_alerts(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.jsonl")
    engine = MonitoringEngine(store=store)
    engine.emit(
        event_type="TEST_EVENT",
        source="test",
        payload={"ok": True},
    )
    engine.inspect_snapshot(
        MonitoringSnapshot(
            timestamp=datetime.now(timezone.utc),
            missing_candles=1,
        )
    )
    assert store.read_events()
    assert store.read_alerts()


def test_prediction_drift_is_deterministic(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    reference = [0.1, 0.2, 0.2, 0.3, 0.4]
    current = [0.6, 0.7, 0.8, 0.9, 1.0]
    first = engine.prediction_drift(reference, current)
    second = engine.prediction_drift(reference, current)
    assert first == second


def test_monitoring_does_not_authorize_execution(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    alerts = engine.inspect_snapshot(
        MonitoringSnapshot(
            timestamp=datetime.now(timezone.utc),
            reconciliation_mismatch=True,
        )
    )
    assert any(alert.severity is AlertSeverity.EMERGENCY for alert in alerts)
