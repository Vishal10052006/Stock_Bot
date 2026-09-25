from __future__ import annotations

from dataclasses import dataclass
import math

from .alerts import AlertSeverity
from .engine import MonitoringEngine
from .health import ComponentHealth
from .models import ModelMonitoringSnapshot, evaluate_model_monitoring
from .risk import RiskMonitoringSnapshot, evaluate_risk_monitoring
from .execution import ExecutionMonitoringSnapshot, evaluate_execution_monitoring
from .strategy import StrategyMonitoringSnapshot, evaluate_strategy_monitoring
from .system import SystemMonitoringSnapshot, evaluate_system_monitoring
from .features import FeatureMonitoringSnapshot, evaluate_feature_monitoring
from .orchestrator import AlertOrchestrator


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Configurable observational thresholds."""

    max_error_rate: float = 0.05
    max_stale_rate: float = 0.10
    max_prediction_psi: float = 0.20
    max_execution_rejection_rate: float = 0.10
    warning_prediction_psi: float = 0.10
    max_feature_psi: float = 0.20
    warning_feature_psi: float = 0.10


class MonitoringPipeline:
    """Unified monitoring evaluator; it has no trading authority."""

    def __init__(
        self,
        engine: MonitoringEngine | None = None,
        policy: MonitoringPolicy | None = None,
        orchestrator: AlertOrchestrator | None = None,
    ):
        self.engine = engine or MonitoringEngine()
        self.policy = policy or MonitoringPolicy()
        self.orchestrator = orchestrator or AlertOrchestrator()

    def record_health(self, health: ComponentHealth) -> None:
        self.engine.record_health(health)

    def record_metric(self, name: str, value: float, **kwargs):
        return self.engine.record_metric(name, value, **kwargs)

    def _alert(self, code: str, component: str, message: str, requested: AlertSeverity | None = None) -> None:
        self.orchestrator.emit(
            self.engine,
            code=code,
            message=message,
            component=component,
            requested_severity=requested,
        )

    def evaluate_system(self, snapshot: SystemMonitoringSnapshot) -> None:
        metrics, alerts = evaluate_system_monitoring(
            snapshot,
            max_error_rate=self.policy.max_error_rate,
            max_stale_rate=self.policy.max_stale_rate,
        )
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"system.{name}", float(value))
        for code in alerts:
            self._alert(code, "system", code, AlertSeverity.CRITICAL)

    def evaluate_features(self, snapshot: FeatureMonitoringSnapshot) -> None:
        metrics, drift, alerts = evaluate_feature_monitoring(
            snapshot,
            max_psi=self.policy.max_feature_psi,
            warning_psi=self.policy.warning_feature_psi,
        )
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"feature.{name}", float(value))
        for report in drift:
            if math.isfinite(float(report.psi)):
                self.engine.record_metric("feature.distribution_psi", report.psi)
        for code in alerts:
            requested = AlertSeverity.CRITICAL if "EXCEEDED" in code else AlertSeverity.WARNING
            self._alert(code, "feature", code, requested)

    def evaluate_model(self, snapshot: ModelMonitoringSnapshot) -> None:
        metrics, drift, alerts = evaluate_model_monitoring(
            snapshot,
            max_psi=self.policy.max_prediction_psi,
            warning_psi=self.policy.warning_prediction_psi,
        )
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"model.{name}", float(value))
        for report in drift:
            self.engine.record_metric("model.prediction_psi", report.psi)
        for code in alerts:
            requested = AlertSeverity.CRITICAL if "EXCEEDED" in code else AlertSeverity.WARNING
            self._alert(code, "model", code, requested)

    def evaluate_performance(self, snapshot) -> None:
        from .performance import evaluate_performance_monitoring

        metrics = evaluate_performance_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"performance.{name}", float(value))

    def evaluate_regime(self, snapshot) -> None:
        from .regime import evaluate_regime_monitoring

        metrics = evaluate_regime_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"regime.{name}", float(value))

    def evaluate_risk(self, snapshot: RiskMonitoringSnapshot) -> None:
        metrics, breaches = evaluate_risk_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"risk.{name}", float(value))
        for code in breaches:
            self._alert(code, "risk", code, AlertSeverity.CRITICAL)

    def evaluate_execution(self, snapshot: ExecutionMonitoringSnapshot) -> None:
        metrics, alerts = evaluate_execution_monitoring(
            snapshot,
            max_rejection_rate=self.policy.max_execution_rejection_rate,
        )
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"execution.{name}", float(value))
        for code in alerts:
            self._alert(code, "execution", code, AlertSeverity.WARNING)

    def evaluate_strategy(self, snapshot: StrategyMonitoringSnapshot) -> None:
        metrics = evaluate_strategy_monitoring(snapshot)
        for name, value in metrics.items():
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                self.engine.record_metric(f"strategy.{name}", float(value))

    def alert_summary(self):
        return self.orchestrator.summary(self.engine.snapshot().alerts)

    def snapshot(self):
        return self.engine.snapshot()
