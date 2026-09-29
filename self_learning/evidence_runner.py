"""Fail-closed evidence-cycle bundle runner.

This module does not execute trading, retraining, backtests, OOS, or paper
engines itself. It binds already-produced immutable artifacts to one candidate
and refuses to manufacture missing evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts import ModelCandidate, PromotionDecision, ValidationSummary
from .validation_orchestrator import ValidationRun


REQUIRED_STAGES = (
    "BACKTEST",
    "LEAKAGE_AUDIT",
    "OOS",
    "WALK_FORWARD",
    "PAPER",
)


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Immutable complete-evidence bundle for one exact candidate."""

    candidate_fingerprint: str
    dataset_version: str
    artifact_fingerprint: str
    validation_run_fingerprint: str
    stages: tuple[ValidationSummary, ...]
    promotion_review: PromotionDecision

    def __post_init__(self) -> None:
        for name, value in (
            ("candidate_fingerprint", self.candidate_fingerprint),
            ("artifact_fingerprint", self.artifact_fingerprint),
            ("validation_run_fingerprint", self.validation_run_fingerprint),
        ):
            if len(value) != 64:
                raise ValueError(f"{name} must be SHA-256")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must not be empty")
        if tuple(stage.stage for stage in self.stages) != REQUIRED_STAGES:
            raise ValueError("stages must contain all required evidence in canonical order")

    @property
    def fingerprint(self) -> str:
        from .contracts import _fingerprint

        return _fingerprint(self)


    def to_dict(self) -> dict[str, object]:
        """Serialize the complete evidence bundle without executing anything."""
        return {
            "candidate_fingerprint": self.candidate_fingerprint,
            "dataset_version": self.dataset_version,
            "artifact_fingerprint": self.artifact_fingerprint,
            "validation_run_fingerprint": self.validation_run_fingerprint,
            "stages": [
                {
                    "stage": stage.stage,
                    "valid": stage.valid,
                    "observations": stage.observations,
                    "metrics": dict(stage.metrics),
                    "limitations": list(stage.limitations),
                    "issues": list(stage.issues),
                    "artifact_fingerprints": list(stage.artifact_fingerprints),
                    "fingerprint": stage.fingerprint,
                }
                for stage in self.stages
            ],
            "promotion_review": {
                "candidate_id": self.promotion_review.candidate_id,
                "candidate_fingerprint": self.promotion_review.candidate_fingerprint,
                "champion_version": self.promotion_review.champion_version,
                "challenger_version": self.promotion_review.challenger_version,
                "state": self.promotion_review.state.value,
                "reasons": list(self.promotion_review.reasons),
                "validation_fingerprints": list(
                    self.promotion_review.validation_fingerprints
                ),
                "approval_reference": self.promotion_review.approval_reference,
                "created_at": self.promotion_review.created_at,
                "fingerprint": self.promotion_review.fingerprint,
            },
            "fingerprint": self.fingerprint,
        }


def build_evidence_bundle(
    candidate: ModelCandidate,
    validation_run: ValidationRun,
    promotion_review: PromotionDecision,
) -> EvidenceBundle:
    """Bind exact candidate, validation run and review evidence.

    The function is deliberately fail-closed: incomplete validation evidence,
    candidate mismatches, or a non-review promotion decision are rejected.
    """
    if not isinstance(candidate, ModelCandidate):
        raise TypeError("candidate must be a ModelCandidate")
    if not isinstance(validation_run, ValidationRun):
        raise TypeError("validation_run must be a ValidationRun")
    if not isinstance(promotion_review, PromotionDecision):
        raise TypeError("promotion_review must be a PromotionDecision")

    if validation_run.candidate_fingerprint != candidate.fingerprint:
        raise ValueError("validation run does not match candidate")
    if promotion_review.candidate_fingerprint != candidate.fingerprint:
        raise ValueError("promotion review does not match candidate")
    if promotion_review.state.value not in {"ELIGIBLE", "BLOCKED"}:
        raise ValueError(
            "promotion review must be an ELIGIBLE or BLOCKED review decision"
        )

    stage_map: Mapping[str, ValidationSummary] = validation_run.stage_map
    missing = [stage for stage in REQUIRED_STAGES if stage not in stage_map]
    if missing:
        raise ValueError(f"missing required evidence stages: {','.join(missing)}")

    invalid = [
        stage
        for stage in REQUIRED_STAGES
        if not stage_map[stage].valid
    ]
    if invalid:
        raise ValueError(
            "cannot build complete evidence bundle from invalid stages: "
            + ",".join(invalid)
        )
    if not validation_run.gate.valid:
        raise ValueError("validation run gate is invalid")
    if promotion_review.state.value != "ELIGIBLE":
        raise ValueError("promotion review is blocked")

    ordered = tuple(stage_map[stage] for stage in REQUIRED_STAGES)
    fingerprints = {
        fingerprint
        for result in ordered
        for fingerprint in result.artifact_fingerprints
    }
    if candidate.artifact_fingerprint not in fingerprints:
        raise ValueError("candidate artifact fingerprint is absent from validation evidence")

    return EvidenceBundle(
        candidate_fingerprint=candidate.fingerprint,
        dataset_version=candidate.dataset_version,
        artifact_fingerprint=candidate.artifact_fingerprint,
        validation_run_fingerprint=validation_run.fingerprint,
        stages=ordered,
        promotion_review=promotion_review,
    )


__all__ = ["EvidenceBundle", "REQUIRED_STAGES", "build_evidence_bundle"]
