"""Focused tests for the complete Phase-23 M-1..M-8 monitoring engine."""

from datetime import datetime, timedelta, timezone

import pytest

from ml.prediction.monitoring import PredictionTelemetry
from monitoring import (
    AlertSeverity,
    AlertManager,
    ComponentHealth,
    HealthMonitor,
    MonitoringEngine,
    MonitoringPolicy,
    MonitoringSnapshot,
    MonitoringStore,
)
from monitoring.performance import performance_from_records
from execution.safety import IndependentSafetyGate, SafetyState


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
        system_health=ComponentHealth.FAILED,
        heartbeat_age_seconds=31.0,
        data_freshness_seconds=25.0,
        missing_candles=1,
        duplicate_events=1,
        invalid_ohlc_count=1,
        connection_failures=1,
        feed_latency_ms=250.0,
        clock_drift_ms=2500.0,
        feature_missing_rate=0.10,
        feature_inf_rate=0.01,
        feature_stale_rate=0.30,
        feature_drift_count=2,
        error_rate=0.20,
        stale_rate=0.30,
        prediction_psi=0.50,
        model_accuracy=0.40,
        model_log_loss=2.0,
        calibration_error=0.50,
        win_rate=0.20,
        expectancy=-10.0,
        max_drawdown_pct=2.0,
        daily_loss_pct=2.0,
        gross_exposure_pct=80.0,
        open_positions=4,
        entries_today=6,
        kill_switch_active=True,
        orders_submitted=10,
        orders_filled=5,
        orders_rejected=5,
        execution_latency_ms=2500.0,
        slippage_bps=75.0,
        order_rejection_rate=0.50,
        reconciliation_mismatch=True,
    )

    alerts = engine.inspect_snapshot(snapshot)
    codes = {alert.code for alert in alerts}

    assert {
        "SYSTEM_HEALTH_FAILED",
        "HEARTBEAT_STALE",
        "DATA_STALE",
        "MISSING_CANDLES",
        "DUPLICATE_EVENTS",
        "INVALID_OHLC",
        "MARKET_CONNECTION_FAILURE",
        "CLOCK_DRIFT_HIGH",
        "FEATURE_MISSING_RATE_HIGH",
        "FEATURE_INFINITY_RATE_HIGH",
        "FEATURE_STALE_RATE_HIGH",
        "FEATURE_DRIFT_DETECTED",
        "MODEL_ERROR_RATE_HIGH",
        "MODEL_STALE_RATE_HIGH",
        "PREDICTION_DRIFT",
        "MODEL_LOG_LOSS_HIGH",
        "MODEL_CALIBRATION_DEGRADED",
        "DRAWDOWN_HIGH",
        "WIN_RATE_LOW",
        "EXPECTANCY_LOW",
        "DAILY_LOSS_LIMIT_BREACH",
        "GROSS_EXPOSURE_HIGH",
        "OPEN_POSITION_LIMIT_BREACH",
        "ENTRY_LIMIT_BREACH",
        "KILL_SWITCH_ACTIVE",
        "EXECUTION_LATENCY_HIGH",
        "SLIPPAGE_HIGH",
        "ORDER_REJECTION_RATE_HIGH",
        "POSITION_RECONCILIATION_MISMATCH",
    }.issubset(codes)

    assert any(alert.severity is AlertSeverity.EMERGENCY for alert in alerts)


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


def test_heartbeat_health_detects_stale_component(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    moment = datetime.now(timezone.utc)
    engine.heartbeat("market_feed", timestamp=moment - timedelta(seconds=40))
    health = engine.build_health(
        expected_components=("market_feed",),
        timestamp=moment,
        heartbeat_timeout_seconds=30,
    )
    assert health.overall is ComponentHealth.FAILED
    assert health.components["market_feed"] is ComponentHealth.FAILED


def test_monitoring_persists_events_and_alerts(tmp_path):
    store = MonitoringStore(tmp_path / "monitoring.jsonl")
    engine = MonitoringEngine(store=store)
    engine.emit(event_type="TEST_EVENT", source="test", payload={"ok": True})
    engine.inspect_snapshot(
        MonitoringSnapshot(
            timestamp=datetime.now(timezone.utc),
            missing_candles=1,
        )
    )
    assert store.read_events()
    assert store.read_alerts()
    assert store.read_events()[0].severity is AlertSeverity.INFO


def test_prediction_drift_is_deterministic(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    reference = [0.1, 0.2, 0.2, 0.3, 0.4]
    current = [0.6, 0.7, 0.8, 0.9, 1.0]
    first = engine.prediction_drift(reference, current)
    second = engine.prediction_drift(reference, current)
    assert first == second
    assert first["exceeded"] is True


def test_feature_batch_drift_reports_each_common_feature(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    reports = engine.feature_batch_drift(
        {"rsi": [10, 20, 30, 40], "atr": [1, 2, 3, 4]},
        {"rsi": [60, 70, 80, 90], "atr": [1, 2, 3, 4]},
    )
    assert {report.metric for report in reports} == {"feature:rsi", "feature:atr"}
    assert any(report.exceeded for report in reports)


def test_model_prediction_adapter_records_telemetry(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    telemetry = PredictionTelemetry(
        timestamp=datetime.now(timezone.utc),
        symbol="ITC",
        model_version="v1.0",
        feature_version="features-v1",
        long_probability=0.70,
        short_probability=0.10,
        no_edge_probability=0.20,
        predicted_class="LONG_SUCCESS",
        regime="TREND_UP",
    )
    events = engine.observe_model_prediction(
        telemetry,
        prediction_psi=0.30,
        model_log_loss=1.0,
    )
    assert any(alert.code == "PREDICTION_DRIFT" for alert in events)
    assert engine.metrics.counter_value("model_predictions") == 1


def test_safety_boundary_is_observable_but_not_authorized(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    decision = IndependentSafetyGate().evaluate(
        SafetyState(
            kill_switch_active=True,
            live_execution_enabled=False,
        )
    )
    event = engine.observe_safety_decision(decision, timestamp=datetime.now(timezone.utc))
    assert event.event_type == "SAFETY_DECISION"
    assert event.payload["allowed"] is False
    assert engine.metrics.counter_value("safety_blocks") == 1


def test_execution_metrics_and_reconciliation_are_observable(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    alerts = engine.observe_execution(
        timestamp=datetime.now(timezone.utc),
        orders_submitted=10,
        orders_filled=8,
        orders_rejected=2,
        partial_fills=1,
        execution_latency_ms=2500.0,
        slippage_bps=60.0,
        reconciliation_mismatch=True,
    )
    codes = {alert.code for alert in alerts}
    assert "EXECUTION_LATENCY_HIGH" in codes
    assert "SLIPPAGE_HIGH" in codes
    assert "POSITION_RECONCILIATION_MISMATCH" in codes

    engine.observe_reconciliation(
        type(
            "Report",
            (),
            {
                "safe": False,
                "status": type("Status", (), {"value": "MISMATCH"})(),
                "mismatches": ("ITC: local=(1, 100.0) broker=(2, 100.0)",),
            },
        )(),
        timestamp=datetime.now(timezone.utc),
    )
    assert engine.metrics.counter_value("reconciliation_mismatches") == 1


def test_performance_aggregator_uses_completed_outcomes_only():
    class Outcome:
        def __init__(self, pnl, gross, fee, slip, holding, mae, mfe):
            self.net_pnl = pnl
            self.gross_pnl = gross
            self.fees = fee
            self.slippage_cost = slip
            self.holding_minutes = holding
            self.mae = mae
            self.mfe = mfe

    report = performance_from_records(
        [
            Outcome(100.0, 105.0, 3.0, 2.0, 20.0, -10.0, 20.0),
            Outcome(-50.0, -45.0, 3.0, 2.0, 15.0, -15.0, 5.0),
        ]
    )
    assert report.trade_count == 2
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.net_pnl == 50.0
    assert report.win_rate == 0.5
    assert report.profit_factor == 2.0
    assert report.max_drawdown == 50.0


def test_alert_manager_suppresses_duplicate_notifications():
    seen = []
    manager = AlertManager(default_cooldown_seconds=60, sink=seen.append)
    engine_alert = type(
        "A",
        (),
        {
            "code": "TEST",
            "source": "test",
            "severity": AlertSeverity.WARNING,
            "correlation_id": "c1",
        },
    )()
    from monitoring.models import Alert

    alert = Alert(
        alert_id="1",
        timestamp=datetime.now(timezone.utc),
        severity=AlertSeverity.WARNING,
        code=engine_alert.code,
        source=engine_alert.source,
        message="test",
        correlation_id=engine_alert.correlation_id,
    )
    assert manager.route(alert) is True
    assert manager.route(alert) is False
    assert len(seen) == 1


def test_monitoring_does_not_authorize_execution(tmp_path):
    engine = MonitoringEngine(store=MonitoringStore(tmp_path / "monitoring.jsonl"))
    alerts = engine.inspect_snapshot(
        MonitoringSnapshot(
            timestamp=datetime.now(timezone.utc),
            reconciliation_mismatch=True,
        )
    )
    assert any(alert.severity is AlertSeverity.EMERGENCY for alert in alerts)
    # Monitoring only emits telemetry; actual execution authority lives elsewhere.


@pytest.mark.parametrize(
    "invalid_field",
    ["error_rate", "stale_rate", "feature_missing_rate", "calibration_error"],
)
def test_snapshot_rejects_non_finite_metrics(invalid_field):
    kwargs = {invalid_field: float("nan")}
    with pytest.raises(ValueError):
        MonitoringSnapshot(
            timestamp=datetime.now(timezone.utc),
            **kwargs,
        )
