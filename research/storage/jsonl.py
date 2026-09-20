"""RB-2 append-only JSONL storage for raw/normalized research artifacts.

This is intentionally dependency-light. It does not replace the project's
existing market-data storage layer and does not touch memory/long_term_memory.
"""
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from research.contracts import ResearchDocument


class JsonlResearchStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, document: ResearchDocument) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            payload = asdict(document)
            for key in ("published_at", "observed_at", "processed_at", "available_at"):
                payload[key] = payload[key].isoformat()
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
