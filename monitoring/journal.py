from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _canonical_timestamp(value: str | datetime | None) -> str:
    timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return timestamp.astimezone(timezone.utc).isoformat()


def _canonical_json(payload: Any) -> str:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("payload must contain JSON-safe values") from exc


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    """Immutable, versioned monitoring telemetry event."""

    event_type: str
    source: str
    timestamp: str
    payload: dict[str, Any]
    severity: str = "INFO"
    correlation_id: str | None = None
    schema_version: str = "MONITORING-EVENT-v1"
    event_id: str = ""

    def __post_init__(self) -> None:
        for name in ("event_type", "source", "severity", "schema_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        canonical_timestamp = _canonical_timestamp(self.timestamp)
        object.__setattr__(self, "timestamp", canonical_timestamp)
        if not isinstance(self.payload, dict):
            raise TypeError("payload must be a dictionary")
        _canonical_json(self.payload)
        if self.correlation_id is not None and not str(self.correlation_id).strip():
            raise ValueError("correlation_id must not be empty")
        if self.event_id != self.computed_event_id:
            raise ValueError("event_id does not match deterministic event identity")

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        severity: str = "INFO",
        correlation_id: str | None = None,
        timestamp: str | datetime | None = None,
        schema_version: str = "MONITORING-EVENT-v1",
    ) -> "MonitoringEvent":
        timestamp_value = _canonical_timestamp(timestamp)
        identity = {
            "event_type": event_type,
            "source": source,
            "timestamp": timestamp_value,
            "payload": payload,
            "severity": severity,
            "correlation_id": correlation_id,
            "schema_version": schema_version,
        }
        event_id = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
        return cls(event_id=event_id, **identity)

    @property
    def computed_event_id(self) -> str:
        identity = {
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "severity": self.severity,
            "correlation_id": self.correlation_id,
            "schema_version": self.schema_version,
        }
        return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "schema_version": self.schema_version,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MonitoringEvent":
        if not isinstance(payload, dict):
            raise ValueError("monitoring event must be an object")
        return cls(
            event_id=str(payload.get("event_id", "")),
            schema_version=str(payload.get("schema_version", "")),
            event_type=str(payload.get("event_type", "")),
            source=str(payload.get("source", "")),
            timestamp=str(payload.get("timestamp", "")),
            severity=str(payload.get("severity", "")),
            correlation_id=payload.get("correlation_id"),
            payload=payload.get("payload", {}),
        )


class MonitoringJournal:
    """Append-only JSONL persistence and deterministic replay for monitoring."""

    def __init__(self, path: str | Path, *, max_records: int | None = None) -> None:
        if max_records is not None and max_records <= 0:
            raise ValueError("max_records must be positive")
        self.path = Path(path)
        self.max_records = max_records

    def append(self, event: MonitoringEvent) -> None:
        if not isinstance(event, MonitoringEvent):
            raise TypeError("event must be a MonitoringEvent")
        existing_ids = {item.event_id for item in self.events()}
        if event.event_id in existing_ids:
            raise ValueError("event_id already exists in monitoring journal")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event.canonical_json() + "\n")

    def events(self) -> tuple[MonitoringEvent, ...]:
        records = list(self._read_all())
        if self.max_records is not None:
            records = records[-self.max_records:]
        return tuple(records)

    def replay(
        self,
        *,
        event_type: str | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
    ) -> tuple[MonitoringEvent, ...]:
        records: Iterable[MonitoringEvent] = self.events()
        if event_type is not None:
            records = (item for item in records if item.event_type == event_type)
        if source is not None:
            records = (item for item in records if item.source == source)
        if correlation_id is not None:
            records = (item for item in records if item.correlation_id == correlation_id)
        return tuple(records)

    def _read_all(self) -> list[MonitoringEvent]:
        if not self.path.exists():
            return []
        records: list[MonitoringEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise ValueError(f"blank monitoring journal line at {line_number}")
                try:
                    payload = json.loads(line)
                    records.append(MonitoringEvent.from_dict(payload))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid monitoring JSONL at line {line_number}"
                    ) from exc
        return records

    def count(self) -> int:
        return len(self._read_all())
