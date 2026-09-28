"""Append-only registry for self-learning experiment lineage.

The implementation reuses the existing ExperimentDefinition, ExperimentRecord,
and LineageRecord contracts. No duplicate experiment model is introduced.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.definition import ExperimentDefinition
from experiments.lineage import LineageRecord
from experiments.record import ExperimentRecord


class ExperimentRegistry:
    """JSONL-backed immutable experiment registry."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(
        self,
        definition: ExperimentDefinition,
        record: ExperimentRecord,
        lineage: LineageRecord,
    ) -> None:
        """Persist one experiment after exact definition/lineage checks."""
        if not isinstance(definition, ExperimentDefinition):
            raise TypeError("definition must be an ExperimentDefinition")
        if not isinstance(record, ExperimentRecord):
            raise TypeError("record must be an ExperimentRecord")
        if not isinstance(lineage, LineageRecord):
            raise TypeError("lineage must be a LineageRecord")

        definition_fp = definition.fingerprint()
        if record.definition_fingerprint != definition_fp:
            raise ValueError("record does not match definition")
        if lineage.definition_fingerprint != definition_fp:
            raise ValueError("lineage does not match definition")
        if lineage.record_fingerprint != record.fingerprint():
            raise ValueError("lineage does not match record")

        for prior in self._read():
            if prior["lineage_id"] == lineage.lineage_id:
                if prior["record_fingerprint"] != lineage.record_fingerprint:
                    raise ValueError("lineage_id collision with different result")
                return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiment_id": definition.experiment_id,
            "definition": definition.to_dict(),
            "definition_fingerprint": definition_fp,
            "record": record.to_dict(),
            "record_fingerprint": record.fingerprint(),
            "lineage": lineage.canonical_payload(),
            "lineage_id": lineage.lineage_id,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")

    def _read(self) -> list[dict[str, object]]:
        """Read raw registry entries for identity checks."""
        if not self.path.exists():
            return []

        result: list[dict[str, object]] = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank experiment registry line {line_number}")
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"experiment registry line {line_number} is not an object")
            result.append(payload)
        return result

    def count(self) -> int:
        """Return the number of persisted experiment executions."""
        return len(self._read())

    def contains(self, lineage_id: str) -> bool:
        """Return whether a lineage identity has already been recorded."""
        return any(item.get("lineage_id") == lineage_id for item in self._read())
