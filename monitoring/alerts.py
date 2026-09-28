from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any

class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"

@dataclass(frozen=True, slots=True)
class Alert:
    """Immutable observational alert."""
    code: str
    severity: AlertSeverity
    message: str
    component: str
    timestamp: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.component.strip() or not self.timestamp.strip():
            raise ValueError("alert identity fields must be non-empty")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def fingerprint(self) -> str:
        payload = {"code": self.code, "severity": self.severity.value, "message": self.message, "component": self.component, "timestamp": self.timestamp, "metadata": self.metadata}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

class AlertManager:
    """Store exact alerts once."""
    def __init__(self) -> None:
        self._alerts: list[Alert] = []
        self._seen: set[str] = set()
    def emit(self, alert: Alert) -> Alert | None:
        if alert.fingerprint in self._seen:
            return None
        self._seen.add(alert.fingerprint)
        self._alerts.append(alert)
        return alert
    def snapshot(self) -> tuple[Alert, ...]:
        return tuple(self._alerts)
    def clear(self) -> None:
        self._alerts.clear()
        self._seen.clear()
