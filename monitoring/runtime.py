from __future__ import annotations

"""Runtime telemetry bridge for the central Monitoring Engine.

Producer telemetry flows one way into Monitoring. This module never authorizes
or rejects trades and never mutates Risk, Strategy, Execution, or Learning.
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
from .integration import MonitoringIntegration, MonitoringIntegrationReport
from .pipeline import MonitoringPipeline
from .performance import PerformanceMonitoringSnapshot
from .regime import RegimeMonitoringSnapshot


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

    def _result(self, component: str, before_metrics: int, before_alerts: int) -> RuntimeTelemetryResult:
        current = self.engine.snapshot()
        return RuntimeTelemetryResult(
            component,
            True,
            len(current.metrics) - before_metrics,
            len(current.alerts) - before_alerts,
        )

    def observe_market(self, metrics: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.record_health(market_health(metrics))
        if getattr(metrics, "quality", None) is not None:
            self.pipeline.record_metric("market.quality", float(metrics.quality))
        self.pipeline.record_metric("market.latency_seconds", float(metrics.latency_seconds))
        return self._result("market_bot", before_metrics, before_alerts)

    def observe_analysis(self, metrics: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.record_health(analysis_health(metrics))
        self.pipeline.record_metric("analysis.feature_count", float(metrics.feature_count))
        self.pipeline.record_metric("analysis.missing_or_invalid", float(metrics.missing_or_invalid))
        self.pipeline.record_metric("analysis.completeness", float(metrics.completeness))
        return self._result("analysis_bot", before_metrics, before_alerts)

    def observe_data_quality(self, snapshot: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_system(data_quality_snapshot(snapshot))
        return self._result("market_data", before_metrics, before_alerts)

    def observe_analysis_quality(self, metrics: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_features(analysis_feature_snapshot(metrics))
        return self._result("analysis_features", before_metrics, before_alerts)

    def observe_model(self, snapshot: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_model(snapshot)
        return self._result("model", before_metrics, before_alerts)

    def observe_strategy(self, snapshot: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_strategy(snapshot)
        return self._result("strategy", before_metrics, before_alerts)

    def observe_risk(self, snapshot: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_risk(snapshot)
        return self._result("risk", before_metrics, before_alerts)

    def observe_execution(self, snapshot: Any) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_execution(snapshot)
        return self._result("execution", before_metrics, before_alerts)

    def observe_performance(self, snapshot: PerformanceMonitoringSnapshot) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_performance(snapshot)
        return self._result("performance", before_metrics, before_alerts)

    def observe_regime(self, snapshot: RegimeMonitoringSnapshot) -> RuntimeTelemetryResult:
        before_metrics = len(self.engine.snapshot().metrics)
        before_alerts = len(self.engine.snapshot().alerts)
        self.pipeline.evaluate_regime(snapshot)
        return self._result("regime", before_metrics, before_alerts)

    def report(self) -> MonitoringIntegrationReport:
        return MonitoringIntegration(self.engine).report()

    def dashboard(self) -> dict[str, Any]:
        return snapshot_payload(self.engine.snapshot())
