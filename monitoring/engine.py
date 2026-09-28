from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .alerts import Alert, AlertManager, AlertSeverity
from .health import ComponentHealth
from .journal import MonitoringEvent, MonitoringJournal
from .metrics import MetricsCollector


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    timestamp: str
    health: tuple[ComponentHealth, ...] = ()
    metrics: dict[str, float | int | bool | None] = field(default_factory=dict)
    alerts: tuple[Alert, ...] = ()

    def __post_init__(self) -> None:
        if not self.timestamp.strip():
            raise ValueError("timestamp must be non-empty")
        object.__setattr__(self, "metrics", dict(self.metrics))
        object.__setattr__(self, "health", tuple(self.health))
        object.__setattr__(self, "alerts", tuple(self.alerts))


class MonitoringEngine:
    """Central observational collection boundary with optional persistence."""

    api_version = "monitoring-v1"

    def __init__(
        self,
        *,
        metrics: MetricsCollector | None = None,
        alerts: AlertManager | None = None,
        journal: MonitoringJournal | None = None,
    ) -> None:
        self.metrics = metrics or MetricsCollector()
        self.alerts = alerts or AlertManager()
        self.journal = journal
        self._health: dict[str, ComponentHealth] = {}

    def record_event(self, event: MonitoringEvent) -> None:
        """Persist one canonical event when a journal is configured."""
        if self.journal is None:
            return
        self.journal.append(event)

    def record_health(self, health: ComponentHealth) -> None:
        self._health[health.component] = health
        if self.journal is not None:
            self.journal.append(
                MonitoringEvent.create(
                    event_type="HEALTH",
                    source=health.component,
                    timestamp=health.observed_at,
                    severity=health.status.value,
                    payload={
                        "message": health.message,
                        "latency_seconds": health.latency_seconds,
                        "metadata": dict(health.metadata or {}),
                    },
                )
            )

    def record_metric(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        timestamp: str | None = None,
    ):
        sample = self.metrics.record(
            name,
            value,
            labels=labels,
            timestamp=timestamp,
        )
        if self.journal is not None:
            self.journal.append(
                MonitoringEvent.create(
                    event_type="METRIC",
                    source=name,
                    timestamp=sample.timestamp,
                    payload={
                        "value": sample.value,
                        "labels": dict(sample.labels or {}),
                    },
                )
            )
        return sample

    def emit_alert(
        self,
        *,
        code: str,
        severity: AlertSeverity,
        message: str,
        component: str,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> Alert | None:
        alert = Alert(
            code,
            severity,
            message,
            component,
            timestamp or datetime.now(timezone.utc).isoformat(),
            metadata,
        )
        emitted = self.alerts.emit(alert)
        if emitted is not None and self.journal is not None:
            self.journal.append(
                MonitoringEvent.create(
                    event_type="ALERT",
                    source=component,
                    timestamp=emitted.timestamp,
                    severity=emitted.severity.value,
                    payload={
                        "code": emitted.code,
                        "message": emitted.message,
                        "metadata": dict(emitted.metadata or {}),
                    },
                )
            )
        return emitted

    def snapshot(self) -> MonitoringSnapshot:
        return MonitoringSnapshot(
            datetime.now(timezone.utc).isoformat(),
            tuple(self._health.values()),
            {s.name: s.value for s in self.metrics.snapshot()},
            self.alerts.snapshot(),
        )

    def reset(self) -> None:
        maximum = self.metrics.max_samples
        self._health.clear()
        self.metrics = MetricsCollector(maximum)
        self.alerts.clear()
