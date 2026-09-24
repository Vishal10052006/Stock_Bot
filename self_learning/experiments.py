"""Thin adapter around the existing experiment contracts.

This module provides the persistent registry that the learning loop lacked.
It deliberately stores the existing frozen ExperimentDefinition and measured
ExperimentRecord identities rather than creating a second experiment engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from experiments.definition import ExperimentDefinition
from experiments.record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class ExperimentArtifact:
    """Immutable definition/result pair with deterministic identity."""

    definition: ExperimentDefinition
    record: ExperimentRecord

    def __post_init__(self) -> None:
        if not isinstance(self.definition, ExperimentDefinition):
            raise TypeError("definition must be an ExperimentDefinition")
        if not isinstance(self.record, ExperimentRecord):
            raise TypeError("record must be an ExperimentRecord")
        if self.record.definition_fingerprint != self.definition.fingerprint():
            raise ValueError("experiment record does not belong to definition")

    @property
    def fingerprint(self) -> str:
        import hashlib

        payload = json.dumps(
            {
                "definition": self.definition.to_dict(),
                "record": self.record.to_dict(),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ExperimentRegistry:
    """Append-only JSONL registry for frozen experiment definitions/results."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def register(
        self,
        definition: ExperimentDefinition,
        record: ExperimentRecord,
    ) -> ExperimentArtifact:
        """Register a complete experiment artifact exactly once."""
        artifact = ExperimentArtifact(definition=definition, record=record)
        existing = self._load()

        for prior in existing:
            if prior.fingerprint == artifact.fingerprint:
                raise ValueError("experiment artifact already registered")
            if prior.definition.experiment_id == definition.experiment_id:
                raise ValueError(
                    "experiment_id already registered with different content"
                )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "fingerprint": artifact.fingerprint,
            "definition": definition.to_dict(),
            "record": record.to_dict(),
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
        return artifact

    def records(self) -> tuple[ExperimentArtifact, ...]:
        """Return all validated experiment artifacts."""
        return tuple(self._load())

    def _load(self) -> list[ExperimentArtifact]:
        if not self.path.exists():
            return []

        artifacts: list[ExperimentArtifact] = []
        for line_no, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                raise ValueError(f"blank experiment registry line {line_no}")

            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"invalid experiment registry line {line_no}")

            definition_payload = payload.get("definition")
            record_payload = payload.get("record")
            if not isinstance(definition_payload, dict):
                raise ValueError(f"missing definition at line {line_no}")
            if not isinstance(record_payload, dict):
                raise ValueError(f"missing record at line {line_no}")

            definition = ExperimentDefinition(
                experiment_id=definition_payload["experiment_id"],
                research_question=definition_payload["research_question"],
                hypothesis=definition_payload["hypothesis"],
                failure_criterion=definition_payload["failure_criterion"],
                dataset_version=definition_payload["dataset_version"],
                code_version=definition_payload["code_version"],
                period_start=definition_payload["period_start"],
                period_end=definition_payload["period_end"],
                symbols=tuple(definition_payload["symbols"]),
                method=definition_payload["method"],
                fixed_parameters=tuple(
                    sorted(
                        (str(key), str(value))
                        for key, value
                        in dict(definition_payload.get("fixed_parameters", {})).items()
                    )
                ),
                allowed_change=tuple(definition_payload.get("allowed_change", ())),
            )

            record = ExperimentRecord(
                definition_fingerprint=record_payload["definition_fingerprint"],
                observations=int(record_payload["observations"]),
                label_distribution=tuple(
                    sorted(
                        (str(key), int(value))
                        for key, value
                        in dict(record_payload.get("label_distribution", {})).items()
                    )
                ),
                baseline_results=record_payload.get("baseline_results", {}),
                model_results=record_payload.get("model_results", {}),
                stratified_results=record_payload.get("stratified_results", {}),
                effective_sample_size_notes=str(
                    record_payload.get("effective_sample_size_notes", "")
                ),
                limitations=tuple(record_payload.get("limitations", ())),
                interpretation=str(record_payload.get("interpretation", "")),
                decision=str(record_payload["decision"]),
                root_cause=str(record_payload.get("root_cause", "")),
                lesson=str(record_payload.get("lesson", "")),
                next_experiment=str(record_payload.get("next_experiment", "")),
            )
            artifact = ExperimentArtifact(definition=definition, record=record)

            stored_fingerprint = payload.get("fingerprint")
            if stored_fingerprint != artifact.fingerprint:
                raise ValueError(
                    f"experiment registry fingerprint mismatch at line {line_no}"
                )

            artifacts.append(artifact)

        return artifacts


__all__ = ["ExperimentArtifact", "ExperimentRegistry"]
