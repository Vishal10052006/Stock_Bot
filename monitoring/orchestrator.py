from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
import hashlib

from .alerts import Alert, AlertSeverity
from .engine import MonitoringEngine


_SEVERITY_ORDER = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.CRITICAL: 2,
    AlertSeverity.EMERGENCY: 3,
}


@dataclass(frozen=True, slots=True)
class AlertRule:
    """Observational alert policy for one alert code."""

    severity: AlertSeverity
    escalation_after: int | None = None
    escalation_severity: AlertSeverity | None = None

    def __post_init__(self) -> None:
        if self.escalation_after is not None and self.escalation_after < 1:
            raise ValueError("escalation_after must be positive")
        if self.escalation_after is None and self.escalation_severity is not None:
            raise ValueError("escalation_severity requires escalation_after")


@dataclass(frozen=True, slots=True)
class AlertSummary:
    """Read-only aggregate of alert activity."""

    total: int
    by_severity: dict[str, int] = field(default_factory=dict)
    by_code: dict[str, int] = field(default_factory=dict)
    active_fingerprints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.total < 0:
            raise ValueError("total must be non-negative")
        object.__setattr__(self, "by_severity", dict(self.by_severity))
        object.__setattr__(self, "by_code", dict(self.by_code))
        object.__setattr__(self, "active_fingerprints", tuple(self.active_fingerprints))


class AlertOrchestrator:
    """
    Centralize alert severity, correlation, repeat escalation and summaries.

    This class is observational only. It never blocks, authorizes, sizes or
    submits trades.
    """

    DEFAULT_RULES: Mapping[str, AlertRule] = {
        "ERROR_RATE_EXCEEDED": AlertRule(AlertSeverity.CRITICAL),
        "STALE_RATE_EXCEEDED": AlertRule(AlertSeverity.CRITICAL),
        "FEATURE_DRIFT_WARNING": AlertRule(AlertSeverity.WARNING),
        "FEATURE_DRIFT_EXCEEDED": AlertRule(AlertSeverity.CRITICAL),
        "PREDICTION_DRIFT_WARNING": AlertRule(AlertSeverity.WARNING),
        "PREDICTION_DRIFT_EXCEEDED": AlertRule(AlertSeverity.CRITICAL),
        "MODEL_LOG_LOSS_EXCEEDED": AlertRule(AlertSeverity.CRITICAL),
        "MODEL_CALIBRATION_DRIFT": AlertRule(AlertSeverity.WARNING),
        "DAILY_LOSS_LIMIT_REACHED": AlertRule(AlertSeverity.CRITICAL),
        "MAX_OPEN_POSITIONS_REACHED": AlertRule(AlertSeverity.CRITICAL),
        "MAX_GROSS_EXPOSURE_REACHED": AlertRule(AlertSeverity.CRITICAL),
        "EXECUTION_REJECTION_RATE_HIGH": AlertRule(AlertSeverity.WARNING),
    }

    def __init__(
        self,
        *,
        rules: Mapping[str, AlertRule] | None = None,
        default_severity: AlertSeverity = AlertSeverity.WARNING,
    ) -> None:
        self.rules = dict(self.DEFAULT_RULES)
        self.rules.update(rules or {})
        self.default_severity = default_severity
        self._occurrences: dict[str, int] = {}

    @staticmethod
    def _correlation_key(code: str, component: str, metadata: Mapping[str, Any] | None) -> str:
        payload = {
            "code": code,
            "component": component,
            "context": dict(metadata or {}),
        }
        # Exclude volatile orchestration fields from correlation identity.
        payload["context"].pop("correlation_id", None)
        payload["context"].pop("occurrence_count", None)
        canonical = repr(sorted(payload.items())).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()[:16]

    def _severity_for(self, code: str, requested: AlertSeverity, count: int) -> AlertSeverity:
        rule = self.rules.get(code)
        if rule is None:
            return requested if _SEVERITY_ORDER[requested] >= _SEVERITY_ORDER[self.default_severity] else self.default_severity

        severity = rule.severity
        if (
            rule.escalation_after is not None
            and rule.escalation_severity is not None
            and count >= rule.escalation_after
            and _SEVERITY_ORDER[rule.escalation_severity] > _SEVERITY_ORDER[severity]
        ):
            severity = rule.escalation_severity
        return severity

    def emit(
        self,
        engine: MonitoringEngine,
        *,
        code: str,
        message: str,
        component: str,
        requested_severity: AlertSeverity | None = None,
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> Alert | None:
        key = self._correlation_key(code, component, metadata)
        count = self._occurrences.get(key, 0) + 1
        self._occurrences[key] = count

        severity = self._severity_for(
            code,
            requested_severity or self.default_severity,
            count,
        )
        enriched = dict(metadata or {})
        enriched.setdefault("correlation_id", key)
        enriched["occurrence_count"] = count

        return engine.emit_alert(
            code=code,
            severity=severity,
            message=message,
            component=component,
            metadata=enriched,
            timestamp=timestamp,
        )

    def summary(self, alerts: tuple[Alert, ...] | list[Alert]) -> AlertSummary:
        by_severity: dict[str, int] = {}
        by_code: dict[str, int] = {}
        fingerprints: list[str] = []
        for alert in alerts:
            severity = alert.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_code[alert.code] = by_code.get(alert.code, 0) + 1
            fingerprints.append(alert.fingerprint)
        return AlertSummary(
            total=len(alerts),
            by_severity=by_severity,
            by_code=by_code,
            active_fingerprints=tuple(fingerprints),
        )

    def reset(self) -> None:
        self._occurrences.clear()
