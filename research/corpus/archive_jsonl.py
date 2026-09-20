"""Read source-native historical archive records from deterministic JSONL."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from research.corpus.archive import HistoricalArchiveRecord


class HistoricalArchiveJsonlLoader:
    """Load immutable archive records without rewriting source timestamps."""

    _REQUIRED = (
        "archive_id", "source_id", "external_id", "title", "content",
        "published_at", "observed_at", "available_at",
    )

    def load(self, path: str | Path) -> tuple[HistoricalArchiveRecord, ...]:
        source_path = Path(path)
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        records: list[HistoricalArchiveRecord] = []
        seen: set[str] = set()
        with source_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("record must be a JSON object")
                    missing = [key for key in self._REQUIRED if key not in payload]
                    if missing:
                        raise ValueError(f"missing fields: {missing}")
                    for key in ("published_at", "observed_at", "available_at", "archived_at"):
                        if payload.get(key) is not None:
                            payload[key] = datetime.fromisoformat(payload[key])
                    payload["symbols"] = tuple(payload.get("symbols", ()))
                    payload["entities"] = tuple(payload.get("entities", ()))
                    record = HistoricalArchiveRecord(**payload)
                except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid historical archive JSONL at line {line_number}") from exc

                if record.archive_id in seen:
                    raise ValueError(f"duplicate archive_id at line {line_number}: {record.archive_id}")
                seen.add(record.archive_id)
                records.append(record)

        return tuple(records)