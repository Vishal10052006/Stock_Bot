from monitoring.engine import MonitoringEngine
from monitoring.runtime import MonitoringRuntime, RuntimeTelemetryResult
from monitoring.models import ModelMonitoringSnapshot
from monitoring.performance import PerformanceMonitoringSnapshot
from monitoring.regime import RegimeMonitoringSnapshot


class Market:
    success=True
    latency_seconds=0.12
    timestamp="2026-01-01T09:15:00+00:00"
    benchmark="NIFTY50"
    availability="AVAILABLE"
    quality=0.99
    regime="TREND"
    market_version="market-v1"


class Analysis:
    success=True
    latency_seconds=0.08
    feature_count=20
    missing_or_invalid=0
    completeness=1.0
    analysis_version="analysis-v1"


def test_runtime_observes_producers_and_exposes_dashboard():
    runtime = MonitoringRuntime(MonitoringEngine())
    assert isinstance(runtime.observe_market(Market()), RuntimeTelemetryResult)
    assert isinstance(runtime.observe_analysis(Analysis()), RuntimeTelemetryResult)
    payload = runtime.dashboard()
    assert payload["health"][0]["component"] == "market_bot"
    assert "market.latency_seconds" in payload["metrics"]


def test_runtime_observes_model_performance_and_regime():
    runtime = MonitoringRuntime(MonitoringEngine())
    runtime.observe_model(ModelMonitoringSnapshot(
        model_version="m1", prediction_count=3,
        labeled_count=3, correct_count=2,
        log_loss=0.2, brier_score=0.1, expected_calibration_error=0.02,
        reference_probabilities=(0.2, 0.4, 0.6),
        current_probabilities=(0.3, 0.5, 0.7),
    ))
    runtime.observe_performance(PerformanceMonitoringSnapshot(
        returns=(0.01, -0.005), trade_pnls=(100.0, -20.0),
        equity_curve=(100000.0, 100500.0, 100480.0),
    ))
    runtime.observe_regime(RegimeMonitoringSnapshot(
        reference=("TREND", "RANGE", "TREND"),
        current=("TREND", "TREND", "TREND"),
    ))
    assert any(k.startswith("model.") for k in runtime.dashboard()["metrics"])
    assert "performance.total_return" in runtime.dashboard()["metrics"]
    assert "regime.reference_count" in runtime.dashboard()["metrics"]


def test_runtime_report_is_observational():
    runtime = MonitoringRuntime(MonitoringEngine())
    report = runtime.report()
    assert report.readiness.status.value in {"READY", "DEGRADED", "BLOCKED", "UNKNOWN"}
    assert report.validation_passed is True
