from monitoring.engine import MonitoringEngine
from monitoring.integration import MonitoringIntegration
from monitoring.performance import (
    PerformanceMonitoringSnapshot,
    evaluate_performance_monitoring,
)
from monitoring.readiness import ReadinessCheck, ReadinessStatus, evaluate_readiness
from monitoring.regime import RegimeMonitoringSnapshot, evaluate_regime_monitoring
from monitoring.validation import validate_monitoring_snapshot


def test_readiness_blocks_on_data_failure():
    assert (
        evaluate_readiness(
            [ReadinessCheck("data.freshness", False, "stale")]
        ).status
        is ReadinessStatus.BLOCKED
    )


def test_performance_metrics():
    result = evaluate_performance_monitoring(
        PerformanceMonitoringSnapshot(
            returns=(0.01, -0.02, 0.03),
            trade_pnls=(10, -5, 15),
            equity_curve=(100, 110, 99, 120),
        )
    )
    assert result["trade_count"] == 3
    assert result["win_rate"] == 2 / 3
    assert result["expectancy"] == 20 / 3
    assert result["max_drawdown"] == 0.1


def test_performance_without_losses_is_monitoring_safe():
    """No-loss performance windows must remain finite-safe."""
    result = evaluate_performance_monitoring(
        PerformanceMonitoringSnapshot(trade_pnls=(10.0, 15.0))
    )
    assert result["win_rate"] == 1.0
    assert result["profit_factor"] is None

    engine = MonitoringEngine()
    for name, value in result.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            engine.record_metric(f"performance.{name}", float(value))

    assert validate_monitoring_snapshot(engine.snapshot()).passed


def test_regime_shift():
    _, alerts = evaluate_regime_monitoring(
        RegimeMonitoringSnapshot(
            reference=("TREND",) * 10,
            current=("RANGE",) * 10,
        )
    )
    assert "NEW_REGIME_DOMINANCE" in alerts


def test_integration_report():
    report = MonitoringIntegration(MonitoringEngine()).report()
    assert report.validation_passed
    assert report.dashboard_payload["alert_summary"]["total"] == 0


def test_validation():
    assert validate_monitoring_snapshot(MonitoringEngine().snapshot()).passed


def test_validation_rejects_null_metric_value():
    snapshot = MonitoringEngine().snapshot()
    snapshot = snapshot.__class__(
        snapshot.timestamp,
        snapshot.health,
        {"bad.metric": None},
        snapshot.alerts,
    )
    result = validate_monitoring_snapshot(snapshot)
    assert not result.passed
    assert "snapshot.metrics.no_null_values" in result.failures
