"""Durable append-only execution audit persistence.

PAPER-05 persists execution lineage without making the audit layer a source of
trading decisions. Records are JSONL, immutable once appended, and keyed by a
deterministic event identity so replay cannot silently duplicate an event.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from execution.engine import ExecutionEvent, Fill, OrderRequest, OrderSnapshot, PositionSnapshot


class DuplicateExecutionAuditError(ValueError):
    """Raised when an identical audit event identity already exists."""


@dataclass(frozen=True, slots=True)
class ExecutionAuditRecord:
    """One durable execution audit record."""

    record_id: str
    record_type: str
    timestamp: pd.Timestamp
    client_order_id: str
    decision_id: str
    purpose: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("audit timestamp must be timezone-aware")
        if not self.record_id.strip():
            raise ValueError("record_id must not be empty")
        if self.record_type not in {"ORDER", "EVENT", "FILL", "POSITION"}:
            raise ValueError("unsupported audit record_type")
        if not self.client_order_id.strip():
            raise ValueError("client_order_id must not be empty")
        object.__setattr__(self, "timestamp", timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "timestamp": self.timestamp.isoformat(),
            "client_order_id": self.client_order_id,
            "decision_id": self.decision_id,
            "purpose": self.purpose,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionAuditRecord":
        return cls(
            record_id=str(data["record_id"]),
            record_type=str(data["record_type"]),
            timestamp=pd.Timestamp(data["timestamp"]),
            client_order_id=str(data["client_order_id"]),
            decision_id=str(data.get("decision_id", "")),
            purpose=str(data.get("purpose", "ENTRY")),
            payload=dict(data.get("payload", {})),
        )


def _canonical(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in value.items()}
    return value


class ExecutionAuditStore:
    """Append-only JSONL store for execution lineage and lifecycle audit."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: ExecutionAuditRecord) -> None:
        if not isinstance(record, ExecutionAuditRecord):
            raise TypeError("record must be an ExecutionAuditRecord")

        if any(item.record_id == record.record_id for item in self.read_all()):
            raise DuplicateExecutionAuditError(
                f"execution audit record already exists: {record.record_id}"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    def read_all(self) -> tuple[ExecutionAuditRecord, ...]:
        if not self.path.exists():
            return ()

        records: list[ExecutionAuditRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ExecutionAuditRecord.from_dict(json.loads(line)))
                except Exception as exc:
                    raise ValueError(
                        f"invalid execution audit record at line {line_number}"
                    ) from exc
        return tuple(records)

    def append_order(self, request: OrderRequest, snapshot: OrderSnapshot) -> None:
        payload = {
            "order": _canonical(asdict(request)),
            "snapshot": _canonical(asdict(snapshot)),
        }
        self._append_derived(
            "ORDER",
            snapshot.updated_at,
            request.client_order_id,
            request.decision_id,
            request.purpose,
            payload,
            suffix=f"ORDER:{snapshot.updated_at.isoformat()}:{snapshot.status.value}",
        )

    def append_event(self, event: ExecutionEvent) -> None:
        payload = _canonical(asdict(event))
        self._append_derived(
            "EVENT",
            event.timestamp,
            event.client_order_id,
            event.decision_id,
            event.purpose,
            payload,
            suffix=(
                f"EVENT:{event.timestamp.isoformat()}:"
                f"{event.from_status}:{event.to_status.value}"
            ),
        )

    def append_fill(self, fill: Fill, *, decision_id: str, purpose: str) -> None:
        payload = _canonical(asdict(fill))
        self._append_derived(
            "FILL",
            fill.timestamp,
            fill.client_order_id,
            decision_id,
            purpose,
            payload,
            suffix=f"FILL:{fill.fill_id}",
        )

    def append_position(
        self,
        position: PositionSnapshot,
        *,
        client_order_id: str,
        decision_id: str,
        purpose: str,
        timestamp: pd.Timestamp,
    ) -> None:
        payload = _canonical(asdict(position))
        self._append_derived(
            "POSITION",
            timestamp,
            client_order_id,
            decision_id,
            purpose,
            payload,
            suffix=(
                f"POSITION:{timestamp.isoformat()}:"
                f"{position.symbol}:{position.quantity}:{position.average_price}"
            ),
        )

    def _append_derived(
        self,
        record_type: str,
        timestamp: pd.Timestamp,
        client_order_id: str,
        decision_id: str,
        purpose: str,
        payload: dict[str, Any],
        *,
        suffix: str,
    ) -> None:
        identity = f"{record_type}|{client_order_id}|{decision_id}|{suffix}"
        record_id = "EA-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        record = ExecutionAuditRecord(
            record_id=record_id,
            record_type=record_type,
            timestamp=timestamp,
            client_order_id=client_order_id,
            decision_id=decision_id,
            purpose=purpose,
            payload=payload,
        )
        try:
            self.append(record)
        except DuplicateExecutionAuditError:
            # Re-observation of the same broker state/event is idempotent.
            return


__all__ = [
    "DuplicateExecutionAuditError",
    "ExecutionAuditRecord",
    "ExecutionAuditStore",
]
