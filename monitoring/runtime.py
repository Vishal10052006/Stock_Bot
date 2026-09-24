from __future__ import annotations

"""Runtime telemetry bridge for the central Monitoring Engine.

This module is deliberately one-way: producer telemetry is translated into
Monitoring observations. It never calls Risk, Strategy, Execution, Learning,
or broker submission code.
"""

from dataclasses import dataclass
from typing import Any

from .adapters import (
    analysis_feature_snapshot,
    analysis_health,
    data_quality_snapshot,
    market_health,
)
from .dashboard import snapshot_payload
from .engine import MonitoringEngine
from .integration import MonitoringIntegrationReport, MonitoringIntegration
from .pipeline import MonitoringPipeline
from .performance import PerformanceMonitoringSnapshot, evaluate_performance_monitoring
from .regime import RegimeMonitoringSnapshot, evaluate_regime_monitoring


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryResult:
    component: str
    observed: bool
    metrics_recorded: int
    alerts_emitted: int


class MonitoringRuntime:
    """Single runtime entry point for producer telemetry -> monitoring."""

    def __init__(self, pipeline: MonitoringPipeline | None = None) -> None:
        self.pipeline = pipeline or MonitoringPipeline()

    @property
    def engine(self) -> MonitoringEngine:
        return self.pipeline.engine

    def observe_market(self, metrics: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.record_health(market_health(metrics))
        if getattr(metrics, "quality", None) is not None:
            self.pipeline.record_metric("market.quality", float(metrics.quality))
        self.pipeline.record_metric("market.latency_seconds", float(metrics.latency_seconds))
        current = self.engine.snapshot()
        return RuntimeTelemetryResult("market_bot", True, len(current.metrics) - before_metrics, len(current.alerts) - before_alerts)

    def observe_analysis(self, metrics: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.record_health(analysis_health(metrics))
        self.pipeline.record_metric("analysis.feature_count", float(metrics.feature_count))
        self.pipeline.record_metric("analysis.missing_or_invalid", float(metrics.missing_or_invalid))
        self.pipeline.record_metric("analysis.completeness", float(metrics.completeness))
        current = self.engine.snapshot()
        return RuntimeTelemetryResult("analysis_bot", True, len(current.metrics) - before_metrics, len(current.alerts) - before_alerts)

    def observe_data_quality(self, snapshot: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_system(data_quality_snapshot(snapshot))
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("market_data", True, len(self.engine.snapshot().metrics), after - before)

    def observe_analysis_quality(self, metrics: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_features(analysis_feature_snapshot(metrics))
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("analysis_features", True, len(self.engine.snapshot().metrics), after - before)

    def observe_model(self, snapshot: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_model(snapshot)
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("model", True, len(self.engine.snapshot().metrics), after - before)

    def observe_strategy(self, snapshot: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_strategy(snapshot)
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("strategy", True, len(self.engine.snapshot().metrics), after - before)

    def observe_risk(self, snapshot: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_risk(snapshot)
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("risk", True, len(self.engine.snapshot().metrics), after - before)

    def observe_execution(self, snapshot: Any) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_execution(snapshot)
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("execution", True, len(self.engine.snapshot().metrics), after - before)

    def observe_performance(self, snapshot: PerformanceMonitoringSnapshot) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        metrics = evaluate_performance_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and value == value:
                self.pipeline.record_metric(f"performance.{name}", float(value))
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("performance", True, len(metrics), after - before)

    def observe_regime(self, snapshot: RegimeMonitoringSnapshot) -> RuntimeTelemetryResult:
        before = len(self.engine.snapshot().alerts)
        metrics, alerts = evaluate_regime_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)):
                self.pipeline.record_metric(f"regime.{name}", float(value))
        for code in alerts:
            requested = None
            requested = __import__("monitoring").AlertSeverity.CRITICAL if code == "NEW_REGIME_DOMINANCE" else __import__("monitoring").AlertSeverity.WARNING
            self.pipeline._alert(code, "regime", code, requested)
        after = len(self.engine.snapshot().alerts)
        return RuntimeTelemetryResult("regime", True, len(metrics), after - before)

    def report(self) -> MonitoringIntegrationReport:
        return MonitoringIntegration(self.engine).report()

    def dashboard(self) -> dict[str, Any]:
        return snapshot_payload(self.engine.snapshot())
