"""Live-readiness gate for the frozen trading specification.

This module only evaluates whether explicitly supplied gates are satisfied.
It never enables live execution and never contacts a broker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.paper_quality import PaperEvidenceQualityReport


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    """Immutable provenance record for one readiness gate."""

    gate: str
    artifact_fingerprint: str
    dataset_version: str
    code_version: str
    validated_at: datetime
    source: str

    def __post_init__(self) -> None:
        for name in (
            "gate",
            "artifact_fingerprint",
            "dataset_version",
            "code_version",
            "source",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.validated_at.tzinfo is None:
            raise ValueError("validated_at must be timezone-aware")

    def canonical_json(self) -> str:
        payload = {
            "gate": self.gate,
            "artifact_fingerprint": self.artifact_fingerprint,
            "dataset_version": self.dataset_version,
            "code_version": self.code_version,
            "validated_at": self.validated_at.isoformat(),
            "source": self.source,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @classmethod
    def from_lineage(
        cls,
        lineage: object,
        *,
        gate: str,
        validated_at: datetime,
    ) -> "ReadinessEvidence":
        """Bind readiness provenance to an existing experiment lineage record.

        The adapter intentionally uses attribute contracts instead of importing
        experiments.lineage at runtime, avoiding the execution/experiments
        import cycle.
        """
        required = (
            "dataset_version",
            "code_version",
            "computed_id",
        )
        if not all(hasattr(lineage, name) for name in required):
            raise TypeError("lineage does not satisfy the lineage provenance contract")

        computed_id = lineage.computed_id()
        if (
            not isinstance(computed_id, str)
            or len(computed_id) != 64
            or any(char not in "0123456789abcdef" for char in computed_id.lower())
        ):
            raise ValueError("lineage.computed_id() must return a SHA-256 hex digest")

        lineage_id = getattr(lineage, "lineage_id", "")
        if lineage_id and lineage_id != computed_id:
            raise ValueError("lineage_id does not match lineage.computed_id()")
        lineage_id = computed_id

        return cls(
            gate=gate,
            artifact_fingerprint=lineage_id,
            dataset_version=lineage.dataset_version,
            code_version=lineage.code_version,
            validated_at=validated_at,
            source=f"lineage:{lineage_id}",
        )


@dataclass(frozen=True, slots=True)
class LiveReadinessInput:
    historical_data_validated: bool
    indicators_validated: bool
    features_leakage_safe: bool
    labels_validated: bool
    baseline_validated: bool
    model_validated: bool
    realistic_backtest_validated: bool
    leakage_audit_passed: bool
    oos_validated: bool
    walk_forward_validated: bool
    paper_evidence_validated: bool
    risk_controls_validated: bool
    monitoring_validated: bool
    kill_switch_validated: bool
    broker_integration_validated: bool
    reconciliation_validated: bool
    compliance_verified_current: bool


@dataclass(frozen=True, slots=True)
class LiveReadinessReport:
    ready: bool
    failed_gates: tuple[str, ...]


class LiveReadinessGate:
    """Fail-closed checklist corresponding to TRADING_SPECIFICATION §26."""

    _FIELDS = (
        "historical_data_validated",
        "indicators_validated",
        "features_leakage_safe",
        "labels_validated",
        "baseline_validated",
        "model_validated",
        "realistic_backtest_validated",
        "leakage_audit_passed",
        "oos_validated",
        "walk_forward_validated",
        "paper_evidence_validated",
        "risk_controls_validated",
        "monitoring_validated",
        "kill_switch_validated",
        "broker_integration_validated",
        "reconciliation_validated",
        "compliance_verified_current",
    )

    def evaluate(
        self,
        gates: LiveReadinessInput,
        *,
        evidence: tuple[ReadinessEvidence, ...] = (),
        require_provenance: bool = False,
        paper_evidence_quality: PaperEvidenceQualityReport | None = None,
    ) -> LiveReadinessReport:
        if not isinstance(gates, LiveReadinessInput):
            raise TypeError("gates must be a LiveReadinessInput")

        failed = [
            field
            for field in self._FIELDS
            if not getattr(gates, field)
        ]
        if paper_evidence_quality is not None:
            valid = getattr(paper_evidence_quality, "valid", None)
            if not isinstance(valid, bool):
                raise TypeError(
                    "paper_evidence_quality must expose a boolean valid property"
                )
            if not valid:
                failed.append("paper_evidence_quality_validated")
        if not isinstance(require_provenance, bool):
            raise TypeError("require_provenance must be a bool")
        if require_provenance:
            if not isinstance(evidence, tuple):
                raise TypeError("evidence must be a tuple of ReadinessEvidence")
            evidence_by_gate: dict[str, ReadinessEvidence] = {}
            for item in evidence:
                if not isinstance(item, ReadinessEvidence):
                    raise TypeError("evidence entries must be ReadinessEvidence")
                if item.gate not in self._FIELDS:
                    raise ValueError(f"unknown readiness evidence gate: {item.gate}")
                if item.gate in evidence_by_gate:
                    raise ValueError(f"duplicate readiness evidence gate: {item.gate}")
                if (
                    len(item.artifact_fingerprint) != 64
                    or any(
                        char not in "0123456789abcdef"
                        for char in item.artifact_fingerprint.lower()
                    )
                ):
                    raise ValueError(
                        f"artifact_fingerprint must be a SHA-256 hex digest: {item.gate}"
                    )
                evidence_by_gate[item.gate] = item
            for field in self._FIELDS:
                if getattr(gates, field) and field not in evidence_by_gate:
                    failed.append(f"{field}_provenance")
        failed = tuple(failed)
        return LiveReadinessReport(
            ready=not failed,
            failed_gates=failed,
        )
