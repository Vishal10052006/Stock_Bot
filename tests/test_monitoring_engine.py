"""Focused tests for the complete Phase-23 M-1..M-8 monitoring engine."""

from datetime import datetime, timedelta, timezone

import pytest

from execution.safety import IndependentSafetyGate, SafetyState
from ml.prediction.monitoring import PredictionTelemetry
from monitoring import (
    AlertManager,
    AlertSeverity,
    ComponentHealth,
    HealthMonitor,
    MonitoringEngine,
    MonitoringPolicy,
    MonitoringSnapshot,
    MonitoringStore,
)
from monitoring.models import Alert
from monitoring.performance import performance_from_records


def test_monitoring_snapshot_emits_cross_domain_alerts(tmp_path):
    engine = MonitoringEngine(
        policy=MonitoringPolicy(
            max_data_freshness_seconds=10.0,
            max_feed_latency_ms=100.0,
            max_prediction_psi=0.20,
            min_model_accuracy=0.50,
            min_win_rate=0.50,
            min_expectancy=0.0,
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