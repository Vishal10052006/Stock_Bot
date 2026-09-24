"""Append-only learning evidence persistence.

This store deliberately does not persist secrets or mutate existing trading
journals.  It is a separate research/governance ledger for self-learning
artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .contracts import (
    DatasetVersion,
    ExperienceBundle,
    ExperimentSpec,
    LearningCycleReport,
    LearningEvidence,
    ModelCandidate,
    PromotionDecision,
)


class DuplicateArtifactError(ValueError):
    """Raised when an identical artifact identity is already present."""


class LearningStore:
    """Append-only JSONL store for self-learning artifacts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _append(self, kind: str, record: Any) -> None:
        """Append one immutable record, rejecting identity conflicts."""
        fingerprint = getattr(record, "fingerprint", None)
        if not fingerprint:
            raise ValueError("learning record must expose a fingerprint")

        for existing_kind, existing in self._read_raw():
            if existing_kind != kind:
                continue
            if existing.get("fingerprint") == fingerprint:
                if existing.get("record") == record_to_dict(record):
                    raise DuplicateArtifactError(f"{kind} already exists")
                raise DuplicateArtifactError(
                    f"{kind} fingerprint collision with different content"
                )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": kind,
            "fingerprint": fingerprint,
            "record": record_to_dict(record),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                + "\n"
            )

    def add_experience_bundle(self, record: ExperienceBundle) -> None:
        self._append("experience_bundle", record)

    def add_evidence(self, record: LearningEvidence) -> None:
        self._append("learning_evidence", record)

    def add_dataset_version(self, record: DatasetVersion) -> None:
        self._append("dataset_version", record)

    def add_experiment(self, record: ExperimentSpec) -> None:
        self._append("experiment", record)

    def add_candidate(self, record: ModelCandidate) -> None:
        self._append("candidate", record)

    def add_promotion_decision(self, record: PromotionDecision) -> None:
        self._append("promotion", record)

    def add_cycle_report(self, record: LearningCycleReport) -> None:
        self._append("cycle", record)

    def _read_raw(self) -> tuple[tuple[str, dict[str, Any]], ...]:
        if not self.path.exists():
            return ()

        records: list[tuple[str, dict[str, Any]]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    raise ValueError(f"blank learning ledger line at {line_no}")
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid learning ledger JSON at line {line_no}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"learning ledger line {line_no} must be an object"
                    )
                kind = payload.get("kind")
                record = payload.get("record")
                if not isinstance(kind, str) or not isinstance(record, dict):
                    raise ValueError(
                        f"invalid learning ledger record at line {line_no}"
                    )
                records.append((kind, payload))
        return tuple(records)

    def records(self, kind: str) -> tuple[dict[str, Any], ...]:
        """Return immutable serialized records of one artifact kind."""
        if not kind.strip():
            raise ValueError("kind must not be empty")
        return tuple(
            payload["record"]
            for existing_kind, payload in self._read_raw()
            if existing_kind == kind
        )

    def count(self, kind: str) -> int:
        """Count one artifact kind."""
        return len(self.records(kind))


def record_to_dict(record: Any) -> dict[str, Any]:
    """Serialize supported self-learning records canonically."""
    if hasattr(record, "to_dict") and callable(record.to_dict):
        value = record.to_dict()
        if isinstance(value, dict):
            return value
    if hasattr(record, "__dataclass_fields__"):
        return {
            field: serialize_value(getattr(record, field))
            for field in record.__dataclass_fields__
        }
    raise TypeError(f"unsupported learning record type: {type(record).__name__}")


def serialize_value(value: Any) -> Any:
    """Recursively serialize enums and immutable mapping containers."""
    if hasattr(value, "value") and hasattr(value, "name"):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): serialize_value(child)
            for key, child in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [serialize_value(child) for child in value]
    if isinstance(value, (set, frozenset)):
        return sorted(serialize_value(child) for child in value)
    return value


class AppendOnlyLearningStore(LearningStore):
    """Public store name used by the Self-Learning Engine."""
