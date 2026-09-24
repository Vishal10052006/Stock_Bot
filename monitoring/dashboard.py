from __future__ import annotations

from typing import Any

from .engine import MonitoringSnapshot


def snapshot_payload(snapshot: MonitoringSnapshot) -> dict[str, Any]:
    """Serialize one monitoring snapshot into a JSON-safe dashboard payload."""
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for alert in snapshot.alerts:
        by_severity[alert.severity.value] = by_severity.get(alert.severity.value, 0) + 1
        by_code[alert.code] = by_code.get(alert.code, 0) + 1

    return {
        "timestamp": snapshot.timestamp,
        "health": [
            {
                "component": health.component,
                "status": health.status.value,
                "observed_at": health.observed_at,
                "message": health.message,
                "latency_seconds": health.latency_seconds,
                "metadata": dict(health.metadata or {}),
            }
            for health in snapshot.health
        ],
        "metrics": dict(snapshot.metrics),
        "alerts": [
            {
                "code": alert.code,
                "severity": alert.severity.value,
                "message": alert.message,
                "component": alert.component,
                "timestamp": alert.timestamp,
                "metadata": dict(alert.metadata or {}),
            }
            for alert in snapshot.alerts
        ],
        "alert_summary": {
            "total": len(snapshot.alerts),
            "by_severity": by_severity,
            "by_code": by_code,
        },
    }
