from monitoring.engine import MonitoringEngine
from monitoring.integration import MonitoringIntegration
from monitoring.performance import PerformanceMonitoringSnapshot, evaluate_performance_monitoring
from monitoring.readiness import ReadinessCheck, ReadinessStatus, evaluate_readiness
from monitoring.regime import RegimeMonitoringSnapshot, evaluate_regime_monitoring
from monitoring.validation import validate_monitoring_snapshot

def test_readiness_blocks_on_data_failure():
    assert evaluate_readiness([ReadinessCheck("data.freshness",False,"stale")]).status is ReadinessStatus.BLOCKED

def test_performance_metrics():
    r=evaluate_performance_monitoring(PerformanceMonitoringSnapshot(returns=(.01,-.02,.03),trade_pnls=(10,-5,15),equity_curve=(100,110,99,120)))
    assert r["trade_count"]==3 and r["win_rate"]==2/3 and r["expectancy"]==20/3 and r["max_drawdown"]==.1

def test_regime_shift():
    _,alerts=evaluate_regime_monitoring(RegimeMonitoringSnapshot(reference=("TREND",)*10,current=("RANGE",)*10))
    assert "NEW_REGIME_DOMINANCE" in alerts

def test_integration_report():
    report=MonitoringIntegration(MonitoringEngine()).report()
    assert report.validation_passed and report.dashboard_payload["alert_summary"]["total"]==0

def test_validation():
    assert validate_monitoring_snapshot(MonitoringEngine().snapshot()).passed


def test_validation_rejects_null_metric_value():
    snapshot=MonitoringEngine().snapshot()
    snapshot=snapshot.__class__(snapshot.timestamp, snapshot.health, {"bad.metric": None}, snapshot.alerts)
    result=validate_monitoring_snapshot(snapshot)
    assert not result.passed
    assert "snapshot.metrics.no_null_values" in result.failures
