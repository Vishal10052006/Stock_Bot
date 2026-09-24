"""Monitoring alert contracts and deduplication.

Alerts are descriptive. They do not execute or reject orders.

References:
    docs/MONITORING_ENGINE.md
    docs/PRODUCTION_CONTROLS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AlertSeverity(StrEnum):
    """Operational alert levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True, slots=True)
class Alert:
    """Immutable alert record."""

    code: str
    severity: AlertSeverity
    message: str
    source: str
    fingerprint: str
    value: float | None = None
    threshold: float | None = None

    def __post_init__(self) -> None:
        """Validate alert identity."""
        if not self.code.strip():
            raise ValueError("alert code must be non-empty")
        if not self.message.strip():
            raise ValueError("alert message must be non-empty")
        if not self.source.strip():
            raise ValueError("alert source must be non-empty")
        if not self.fingerprint.strip():
            raise ValueError("alert fingerprint must be non-empty")


class AlertEngine:
    """Build and deduplicate active alerts."""

    def __init__(self) -> None:
        """Initialize active alerts."""
        self._active: dict[str, Alert] = {}

    def emit(
        self,
        *,
        code: str,
        severity: AlertSeverity,
        message: str,
        source: str,
        fingerprint: str,
        value: float | None = None,
        threshold: float | None = None,
    ) -> Alert | None:
        """Emit one alert unless the fingerprint is already active."""
        if fingerprint in self._active:
            return None

        alert = Alert(
            code=code,
            severity=severity,
            message=message,
            source=source,
            fingerprint=fingerprint,
            value=value,
            threshold=threshold,
        )
        self._active[fingerprint] = alert
        return alert

    def clear(self, fingerprint: str) -> None:
        """Clear one active alert."""
        self._active.pop(fingerprint, None)

    def clear_code(self, code: str) -> None:
        """Clear all active alerts for one code."""
        for fingerprint in tuple(self._active):
            if self._active[fingerprint].code == code:
                self._active.pop(fingerprint, None)

    def active(self) -> tuple[Alert, ...]:
        """Return active alerts in deterministic severity order."""
        order = {
            AlertSeverity.EMERGENCY: 0,
            AlertSeverity.CRITICAL: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.INFO: 3,
        }
        return tuple(
            sorted(
                self._active.values(),
                key=lambda alert: (
                    order[alert.severity],
                    alert.code,
                    alert.fingerprint,
                ),
            )
        )
