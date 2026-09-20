"""Append-only JSONL research storage with deterministic replay."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from research.contracts import ResearchDocument


class JsonlResearchStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, document: ResearchDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(document)
        for key in ("published_at", "observed_at", "processed_at", "available_at"):
            payload[key] = payload[key].isoformat()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def read(self) -> tuple[ResearchDocument, ...]:
        if not self.path.exists():
            return ()
        rows = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    for key in ("published_at", "observed_at", "processed_at", "available_at"):
                        payload[key] = datetime.fromisoformat(payload[key])
                    payload["symbols"] = tuple(payload.get("symbols", ()))
                    payload["entities"] = tuple(payload.get("entities", ()))
                    rows.append(ResearchDocument(**payload))
                except (TypeError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid research JSONL at line {line_number}") from exc
        return tuple(rows)

    def deduplicated(self) -> tuple[ResearchDocument, ...]:
        unique = {document.document_id: document for document in self.read()}
        return tuple(sorted(unique.values(), key=lambda d: (d.available_at, d.document_id)))
