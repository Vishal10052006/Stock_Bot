"""Append-only persistence for reproducible paper-trading evidence records.

The journal stores immutable evidence records as JSON Lines. Existing records are
never rewritten; every loaded record is revalidated against its deterministic
identity and content fingerprint.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .paper_evidence import PaperEvidenceSnapshot


@dataclass(frozen=True, slots=True)
class PaperEvidenceRecord:
    """Immutable evidence record for one reproducible paper-trading run."""

    run_id: str
    evidence: PaperEvidenceSnapshot
    period_start: str
    period_end: str
    source_run_id: str
    record_version: str = "PAPER-RECORD-v1"

    def __post_init__(self) -> None:
        for name in ("run_id", "source_run_id", "record_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")

        start = pd.Timestamp(self.period_start)
        end = pd.Timestamp(self.period_end)
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("period_start and period_end must be timezone-aware")
        if end < start:
            raise ValueError("period_end cannot precede period_start")

        if self.run_id != self.computed_run_id:
            raise ValueError("run_id does not match deterministic record identity")

    @classmethod
    def create(
        cls,
        *,
        evidence: PaperEvidenceSnapshot,
        period_start: object,
        period_end: object,
        source_run_id: str,
        record_version: str = "PAPER-RECORD-v1",
    ) -> "PaperEvidenceRecord":
        """Create a record with a deterministic run identity."""
        start = _canonical_timestamp(period_start)
        end = _canonical_timestamp(period_end)
        payload = {
            "record_version": record_version,
            "evidence_fingerprint": evidence.fingerprint,
            "period_start": start,
            "period_end": end,
            "source_run_id": source_run_id,
        }
        run_id = _sha256(payload)
        return cls(
            run_id=run_id,
            evidence=evidence,
            period_start=start,
            period_end=end,
            source_run_id=source_run_id,
            record_version=record_version,
        )

    @property
    def computed_run_id(self) -> str:
        return _sha256(
            {
                "record_version": self.record_version,
                "evidence_fingerprint": self.evidence.fingerprint,
                "period_start": self.period_start,
                "period_end": self.period_end,
                "source_run_id": self.source_run_id,
            }
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "record_version": self.record_version,
            "evidence": json.loads(self.evidence.canonical_json()),
            "period_start": self.period_start,
            "period_end": self.period_end,
            "source_run_id": self.source_run_id,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return self.canonical_payload()

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "PaperEvidenceRecord":
        """Rebuild and validate one serialized record."""
        evidence_payload = payload.get("evidence")
        if not isinstance(evidence_payload, dict):
            raise ValueError("record evidence must be an object")

        evidence = PaperEvidenceSnapshot(**evidence_payload)
        record = cls(
            run_id=str(payload.get("run_id", "")),
            evidence=evidence,
            period_start=str(payload.get("period_start", "")),
            period_end=str(payload.get("period_end", "")),
            source_run_id=str(payload.get("source_run_id", "")),
            record_version=str(payload.get("record_version", "PAPER-RECORD-v1")),
        )
        return record


class PaperEvidenceJournal:
    """Append-only JSONL journal for reproducible paper evidence."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: PaperEvidenceRecord) -> None:
        """Append one record, rejecting duplicate or conflicting run identities."""
        if not isinstance(record, PaperEvidenceRecord):
            raise TypeError("record must be a PaperEvidenceRecord")

        existing = self._load_records()
        for prior in existing:
            if prior.run_id == record.run_id:
                if prior.fingerprint == record.fingerprint:
                    raise ValueError("run_id already exists in journal")
                raise ValueError("run_id collision with different record content")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.canonical_json() + "\n")

    def records(self) -> tuple[PaperEvidenceRecord, ...]:
        """Load and validate all records without mutating the journal."""
        return tuple(self._load_records())

    def _load_records(self) -> list[PaperEvidenceRecord]:
        if not self.path.exists():
            return []

        records: list[PaperEvidenceRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    raise ValueError(f"blank journal line at {line_number}")
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid JSON at journal line {line_number}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise ValueError(f"journal line {line_number} must be an object")
                records.append(PaperEvidenceRecord.from_dict(payload))

        return records


def _canonical_timestamp(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError("period timestamps must be timezone-aware")
    return timestamp.isoformat()


def _sha256(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def iter_evidence_fingerprints(
    records: Iterable[PaperEvidenceRecord],
) -> tuple[str, ...]:
    """Return deterministic fingerprints for an iterable of validated records."""
    return tuple(record.fingerprint for record in records)
