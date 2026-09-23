"""AB-45/Phase-16 append-only trade-memory persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .models import TradeDecisionRecord, TradeJournalRecord

JournalEvent = Union[TradeDecisionRecord, TradeJournalRecord]


class DuplicateJournalRecordError(ValueError):
    """Raised when a journal trade identity already exists."""


class TradeJournalStore:
    """JSONL-backed append-only store for decision and outcome events.

    Existing outcome-only journals remain readable. New decision events are
    stored alongside outcomes and linked by trade_id.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: JournalEvent) -> None:
        if not isinstance(record, (TradeDecisionRecord, TradeJournalRecord)):
            raise TypeError("record must be a TradeDecisionRecord or TradeJournalRecord")

        existing_ids = {item.trade_id for item in self.read_events()}
        if record.trade_id in existing_ids:
            raise DuplicateJournalRecordError(
                f"journal trade_id already exists: {record.trade_id}"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    def append_outcome(self, record: TradeJournalRecord) -> None:
        """Append an outcome using the legacy method name."""
        self.append(record)

    def read_events(self) -> tuple[JournalEvent, ...]:
        if not self.path.exists():
            return ()

        records: list[JournalEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record_type = data.get("record_type", "outcome")
                    if record_type == "decision":
                        records.append(TradeDecisionRecord.from_dict(data))
                    elif record_type == "outcome":
                        records.append(TradeJournalRecord.from_dict(data))
                    else:
                        raise ValueError(f"unknown record_type {record_type!r}")
                except Exception as exc:
                    raise ValueError(f"invalid journal record at line {line_number}") from exc
        return tuple(records)

    def read_all(self) -> tuple[TradeJournalRecord, ...]:
        """Return completed outcomes for backward-compatible consumers."""
        return tuple(item for item in self.read_events() if isinstance(item, TradeJournalRecord))

    def read_decisions(self) -> tuple[TradeDecisionRecord, ...]:
        """Return all decision snapshots, including NO_TRADE decisions."""
        return tuple(item for item in self.read_events() if isinstance(item, TradeDecisionRecord))

    def count(self) -> int:
        return len(self.read_events())

    def decision_count(self) -> int:
        return len(self.read_decisions())
