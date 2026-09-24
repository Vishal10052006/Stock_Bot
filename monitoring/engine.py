from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from .alerts import Alert, AlertManager, AlertSeverity
from .health import ComponentHealth
from .metrics import MetricsCollector

@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    timestamp: str
    health: tuple[ComponentHealth, ...] = ()
    metrics: dict[str, float | int | bool | None] = field(default_factory=dict)
    alerts: tuple[Alert, ...] = ()
    def __post_init__(self) -> None:
        if not self.timestamp.strip(): raise ValueError("timestamp must be non-empty")
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "health", tuple(self.health))
        object.__setattr__(self, "alerts", tuple(self.alerts))

class MonitoringEngine:
    """Central collection boundary; observational only."""
    api_version = "monitoring-v1"
    def __init__(self, *, metrics: MetricsCollector | None = None, alerts: AlertManager | None = None) -> None:
        self.metrics = metrics or MetricsCollector()
        self.alerts = alerts or AlertManager()
        self._health: dict[str, ComponentHealth] = {}
    def record_health(self, health: ComponentHealth) -> None: self._health[health.component] = health
    def record_metric(self, name: str, value: float, *, labels: dict[str, str] | None = None, timestamp: str | None = None):
        return self.metrics.record(name, value, labels=labels, timestamp=timestamp)
    def emit_alert(self, *, code: str, severity: AlertSeverity, message: str, component: str, metadata: dict[str, Any] | None = None, timestamp: str | None = None) -> Alert | None:
        return self.alerts.emit(Alert(code, severity, message, component, timestamp or datetime.now(timezone.utc).isoformat(), metadata))
    def snapshot(self) -> MonitoringSnapshot:
        return MonitoringSnapshot(datetime.now(timezone.utc).isoformat(), tuple(self._health.values()), {s.name: s.value for s in self.metrics.snapshot()}, self.alerts.snapshot())
    def reset(self) -> None:
        maximum = self.metrics.max_samples
        self._health.clear(); self.metrics = MetricsCollector(maximum); self.alerts.clear()
