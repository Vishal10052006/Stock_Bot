"""S27 reproducibility and experiment lineage contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .definition import ExperimentDefinition
from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class LineageRecord:
    """Immutable lineage connecting definition, result, data and code."""

    experiment_id: str
    definition_fingerprint: str
    record_fingerprint: str
    dataset_version: str
    code_version: str
    artifact_fingerprints: tuple[tuple[str, str], ...] = ()
    parent_lineage_ids: tuple[str, ...] = ()
    lineage_id: str = ""

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id must not be empty")
        if len(self.definition_fingerprint) != 64:
            raise ValueError("definition_fingerprint must be SHA-256")
        if len(self.record_fingerprint) != 64:
            raise ValueError("record_fingerprint must be SHA-256")
        if not self.dataset_version.strip() or not self.code_version.strip():
            raise ValueError("dataset_version and code_version are required")
        keys = [key for key, _ in self.artifact_fingerprints]
        if len(keys) != len(set(keys)):
            raise ValueError("artifact fingerprint keys must be unique")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "definition_fingerprint": self.definition_fingerprint,
            "record_fingerprint": self.record_fingerprint,
            "dataset_version": self.dataset_version,
            "code_version": self.code_version,
            "artifact_fingerprints": dict(self.artifact_fingerprints),
            "parent_lineage_ids": list(self.parent_lineage_ids),
        }

    def computed_id(self) -> str:
        payload = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def with_computed_id(self) -> "LineageRecord":
        return LineageRecord(
            experiment_id=self.experiment_id,
            definition_fingerprint=self.definition_fingerprint,
            record_fingerprint=self.record_fingerprint,
            dataset_version=self.dataset_version,
            code_version=self.code_version,
            artifact_fingerprints=self.artifact_fingerprints,
            parent_lineage_ids=self.parent_lineage_ids,
            lineage_id=self.computed_id(),
        )


def build_lineage(
    definition: ExperimentDefinition,
    record: ExperimentRecord,
    *,
    artifact_fingerprints: dict[str, str] | None = None,
    parent_lineage_ids: tuple[str, ...] = (),
) -> LineageRecord:
    """Bind an experiment record to its exact definition/data/code identity."""
    if not isinstance(definition, ExperimentDefinition):
        raise TypeError("definition must be an ExperimentDefinition")
    if not isinstance(record, ExperimentRecord):
        raise TypeError("record must be an ExperimentRecord")
    if record.definition_fingerprint != definition.fingerprint():
        raise ValueError("record does not belong to definition")

    return LineageRecord(
        experiment_id=definition.experiment_id,
        definition_fingerprint=definition.fingerprint(),
        record_fingerprint=record.fingerprint(),
        dataset_version=definition.dataset_version,
        code_version=definition.code_version,
        artifact_fingerprints=tuple(
            sorted((str(k), str(v)) for k, v in (artifact_fingerprints or {}).items())
        ),
        parent_lineage_ids=tuple(parent_lineage_ids),
    ).with_computed_id()
