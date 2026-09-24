"""Phase-20 immutable model registry.

The registry stores versioned model metadata and artifact identity. It is a
research/governance boundary only: registration never mutates a model,
strategy, risk configuration, or execution state, and no registration path
submits orders or enables live trading.

References:
    Phase 9 model registry contract.
    Phase 20 Model Registry roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping


class ModelRegistryStatus(str, Enum):
    """Lifecycle state recorded by the registry."""

    RESEARCH_ONLY = "RESEARCH_ONLY"
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    RETIRED = "RETIRED"


def _require_text(value: str, field_name: str) -> str:
    """Validate and normalize required textual registry fields."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_sha256(value: str, field_name: str) -> str:
    """Validate a lowercase hexadecimal SHA-256 identity."""
    value = _require_text(value, field_name).lower()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a SHA-256 hex digest")
    return value


def _canonical_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a mapping into deterministic JSON-compatible metadata."""
    if not isinstance(value, Mapping):
        raise TypeError("registry metadata must be a mapping")
    return {str(key): value[key] for key in sorted(value, key=str)}


@dataclass(frozen=True, slots=True)
class ModelRegistryRecord:
    """Immutable versioned model artifact metadata.

    This supersedes the original Phase-9 metadata-only contract while keeping
    its required provenance fields compatible with existing callers.
    """

    model_version: str
    model_family: str
    feature_version: str
    dataset_version: str
    code_version: str
    training_period_start: str
    training_period_end: str
    validation_period_start: str
    validation_period_end: str
    test_period_start: str
    test_period_end: str
    hyperparameters: Mapping[str, object]
    metrics: Mapping[str, float]
    approval_status: str = ModelRegistryStatus.RESEARCH_ONLY.value
    artifact_uri: str = ""
    artifact_fingerprint: str = ""
    strategy_version: str = ""
    lineage_id: str = ""
    evaluation_fingerprint: str = ""
    approval_reference: str = ""

    def __post_init__(self) -> None:
        """Fail closed on incomplete provenance or invalid lifecycle state."""
        text_fields = (
            ("model_version", self.model_version),
            ("model_family", self.model_family),
            ("feature_version", self.feature_version),
            ("dataset_version", self.dataset_version),
            ("code_version", self.code_version),
            ("training_period_start", self.training_period_start),
            ("training_period_end", self.training_period_end),
            ("validation_period_start", self.validation_period_start),
            ("validation_period_end", self.validation_period_end),
            ("test_period_start", self.test_period_start),
            ("test_period_end", self.test_period_end),
        )
        for field_name, value in text_fields:
            _require_text(value, field_name)

        if self.approval_status not in {status.value for status in ModelRegistryStatus}:
            raise ValueError("invalid approval_status")

        if self.artifact_uri:
            _require_text(self.artifact_uri, "artifact_uri")
        if self.artifact_fingerprint:
            _require_sha256(self.artifact_fingerprint, "artifact_fingerprint")
        if self.lineage_id:
            _require_sha256(self.lineage_id, "lineage_id")
        if self.evaluation_fingerprint:
            _require_sha256(self.evaluation_fingerprint, "evaluation_fingerprint")

        if self.approval_status == ModelRegistryStatus.APPROVED.value:
            if not self.artifact_fingerprint:
                raise ValueError("approved model requires artifact_fingerprint")
            if not self.lineage_id:
                raise ValueError("approved model requires lineage_id")
            if not self.evaluation_fingerprint:
                raise ValueError("approved model requires evaluation_fingerprint")
            if not self.approval_reference.strip():
                raise ValueError("approved model requires approval_reference")

        if not isinstance(self.hyperparameters, Mapping):
            raise TypeError("hyperparameters must be a mapping")
        if not isinstance(self.metrics, Mapping):
            raise TypeError("metrics must be a mapping")

        for key, value in self.metrics.items():
            if not isinstance(key, str):
                raise TypeError("metric names must be strings")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("metrics must contain numeric values")

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic registry metadata."""
        return {
            "model_version": self.model_version,
            "model_family": self.model_family,
            "feature_version": self.feature_version,
            "dataset_version": self.dataset_version,
            "code_version": self.code_version,
            "training_period_start": self.training_period_start,
            "training_period_end": self.training_period_end,
            "validation_period_start": self.validation_period_start,
            "validation_period_end": self.validation_period_end,
            "test_period_start": self.test_period_start,
            "test_period_end": self.test_period_end,
            "hyperparameters": _canonical_mapping(self.hyperparameters),
            "metrics": _canonical_mapping(self.metrics),
            "approval_status": self.approval_status,
            "artifact_uri": self.artifact_uri,
            "artifact_fingerprint": self.artifact_fingerprint,
            "strategy_version": self.strategy_version,
            "lineage_id": self.lineage_id,
            "evaluation_fingerprint": self.evaluation_fingerprint,
            "approval_reference": self.approval_reference,
        }

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity for the complete registry record."""
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelApproval:
    """Explicit governance evidence required to mark a model approved."""

    model_fingerprint: str
    approval_reference: str
    evaluator: str
    approved_at: str

    def __post_init__(self) -> None:
        _require_sha256(self.model_fingerprint, "model_fingerprint")
        _require_text(self.approval_reference, "approval_reference")
        _require_text(self.evaluator, "evaluator")
        _require_text(self.approved_at, "approved_at")

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity for the approval evidence."""
        payload = {
            "model_fingerprint": self.model_fingerprint,
            "approval_reference": self.approval_reference,
            "evaluator": self.evaluator,
            "approved_at": self.approved_at,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


class ModelRegistry:
    """Immutable-version registry with explicit, non-automatic approval.

    Registration is append-only by model version. Re-registering a version with
    different metadata is rejected. Approval creates a new immutable record and
    requires explicit governance evidence; it is never inferred from metrics.
    """

    def __init__(
        self,
        records: Mapping[str, ModelRegistryRecord] | None = None,
    ) -> None:
        self._records = dict(records or {})
        self._history = {
            version: (record,)
            for version, record in self._records.items()
        }

    def register(self, record: ModelRegistryRecord) -> ModelRegistryRecord:
        """Register a research/candidate record without promotion."""
        if not isinstance(record, ModelRegistryRecord):
            raise TypeError("record must be a ModelRegistryRecord")
        if record.approval_status == ModelRegistryStatus.APPROVED.value:
            raise ValueError(
                "approved models must be registered through approve(); "
                "direct approval is forbidden"
            )

        existing = self._records.get(record.model_version)
        if existing is not None:
            if existing.fingerprint != record.fingerprint:
                raise ValueError(
                    f"model version already registered with different metadata: "
                    f"{record.model_version}"
                )
            return existing

        self._records[record.model_version] = record
        self._history[record.model_version] = (
            *self._history.get(record.model_version, ()),
            record,
        )
        return record

    def approve(self, model_version: str, approval: ModelApproval) -> ModelRegistryRecord:
        """Create an approved immutable record from explicit governance evidence."""
        current = self.get(model_version)
        if current.approval_status == ModelRegistryStatus.RETIRED.value:
            raise ValueError("retired model cannot be approved")
        if not current.artifact_fingerprint:
            raise ValueError("model must have an artifact_fingerprint before approval")
        if not current.lineage_id:
            raise ValueError("model must have a lineage_id before approval")
        if not current.evaluation_fingerprint:
            raise ValueError("model must have an evaluation_fingerprint before approval")

        if approval.model_fingerprint != current.fingerprint:
            raise ValueError("approval evidence does not match registered model")

        approved = ModelRegistryRecord(
            **{
                **current.to_dict(),
                "approval_status": ModelRegistryStatus.APPROVED.value,
                "approval_reference": approval.approval_reference,
            }
        )
        self._records[model_version] = approved
        self._history[model_version] = (
            *self._history.get(model_version, ()),
            approved,
        )
        return approved

    def retire(self, model_version: str, *, reason: str) -> ModelRegistryRecord:
        """Retire a version without deleting its historical identity."""
        current = self.get(model_version)
        _require_text(reason, "reason")
        retired = ModelRegistryRecord(
            **{
                **current.to_dict(),
                "approval_status": ModelRegistryStatus.RETIRED.value,
            }
        )
        self._records[model_version] = retired
        self._history[model_version] = (
            *self._history.get(model_version, ()),
            retired,
        )
        return retired

    def get(self, model_version: str) -> ModelRegistryRecord:
        """Return the exact registered version."""
        try:
            return self._records[model_version]
        except KeyError as exc:
            raise KeyError(f"unknown model version: {model_version}") from exc

    def versions(self) -> tuple[str, ...]:
        """Return all registered versions in deterministic order."""
        return tuple(sorted(self._records))

    def history(self, model_version: str) -> tuple[ModelRegistryRecord, ...]:
        """Return every immutable state recorded for one model version."""
        if model_version not in self._history:
            raise KeyError(f"unknown model version: {model_version}")
        return self._history[model_version]

    def by_status(self, status: ModelRegistryStatus) -> tuple[ModelRegistryRecord, ...]:
        """Return records with one exact lifecycle status."""
        if not isinstance(status, ModelRegistryStatus):
            raise TypeError("status must be a ModelRegistryStatus")
        return tuple(
            self._records[version]
            for version in self.versions()
            if self._records[version].approval_status == status.value
        )


__all__ = [
    "ModelApproval",
    "ModelRegistry",
    "ModelRegistryRecord",
    "ModelRegistryStatus",
]
