"""Append-only JSONL persistence for monitoring events and alerts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
from typing import Iterable

from monitoring.models import Alert, AlertSeverity, MonitoringEvent


class MonitoringStore:
    """Local append-only evidence store for MonitoringEngine."""

    def __init__(self, path: str | Path = "memory/monitoring/events.jsonl") -> None:
        self.path = Path(path)

    def append_event(self, event: MonitoringEvent) -> None:
        """Persist one immutable telemetry event."""
        if not isinstance(event, MonitoringEvent):
            raise TypeError("event must be MonitoringEvent")
        self._append({"record_type": "event", **self._serialize(event)})

    def append_alert(self, alert: Alert) -> None:
        """Persist one immutable alert."""
        if not isinstance(alert, Alert):
            raise TypeError("alert must be Alert")
        self._append({"record_type": "alert", **self._serialize(alert)})

    def read_events(self) -> tuple[MonitoringEvent, ...]:
        """Read persisted telemetry events in append order."""
        result = []
        for item in self._read("event"):
            result.append(
                MonitoringEvent(
                    event_id=item["event_id"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    event_type=item["event_type"],
                    source=item["source"],
                    severity=AlertSeverity(item["severity"]),
                    symbol=item.get("symbol"),
                    correlation_id=item.get("correlation_id"),
                    payload=item.get("payload", {}),
                )
            )
        return tuple(result)

    def read_alerts(self) -> tuple[Alert, ...]:
        """Read persisted alerts in append order."""
        result = []
        for item in self._read("alert"):
            result.append(
                Alert(
                    alert_id=item["alert_id"],
                    timestamp=datetime.fromisoformat(item["timestamp"]),
                    severity=AlertSeverity(item["severity"]),
                    code=item["code"],
                    source=item["source"],
                    message=item["message"],
                    correlation_id=item.get("correlation_id"),
                    details=item.get("details", {}),
                )
            )
        return tuple(result)

    def _append(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
            )
            handle.write("\n")

    def _read(self, record_type: str) -> Iterable[dict]:
        if not self.path.exists():
            return ()
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if payload.get("record_type") == record_type:
                    records.append(payload)
        return records

    @staticmethod
    def _serialize(value):
        if isinstance(value, MonitoringEvent):
            return {
                "event_id": value.event_id,
                "timestamp": value.timestamp.isoformat(),
                "event_type": value.event_type,
                "source": value.source,
                "severity": value.severity.value,
                "symbol": value.symbol,
                "correlation_id": value.correlation_id,
                "payload": dict(value.payload),
            }
        return {
            "alert_id": value.alert_id,
            "timestamp": value.timestamp.isoformat(),
            "severity": value.severity.value,
            "code": value.code,
            "source": value.source,
            "message": value.message,
            "correlation_id": value.correlation_id,
            "details": dict(value.details),
        }
