"""Controlled lifecycle management for self-learning model candidates.

SL-24 connects verified retraining outputs to the existing immutable
ModelCandidate contract and LearningStore. It does not approve, deploy, or
execute models.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from typing import Mapping

from .contracts import (
    CandidateLifecycle,
    DatasetVersion,
    ExperimentSpec,
    ModelCandidate,
    PromotionDecision,
    PromotionState,
)
from .retraining import RetrainingResult
from .store import LearningStore


_ALLOWED_TRANSITIONS: dict[CandidateLifecycle, frozenset[CandidateLifecycle]] = {
    CandidateLifecycle.CANDIDATE: frozenset(
        {CandidateLifecycle.VALIDATING, CandidateLifecycle.REJECTED}
    ),
    CandidateLifecycle.VALIDATING: frozenset(
        {CandidateLifecycle.PAPER, CandidateLifecycle.REJECTED}
    ),
    CandidateLifecycle.PAPER: frozenset(
        {CandidateLifecycle.PROMOTION_REVIEW, CandidateLifecycle.REJECTED}
    ),
    CandidateLifecycle.PROMOTION_REVIEW: frozenset(
        {CandidateLifecycle.REJECTED}
    ),
    CandidateLifecycle.PROMOTED: frozenset({CandidateLifecycle.RETIRED}),
    CandidateLifecycle.REJECTED: frozenset(),
    CandidateLifecycle.RETIRED: frozenset(),
}


def _lineage_id(
    *,
    parent_model_version: str,
    experiment_fingerprint: str,
    dataset_version: str,
    artifact_fingerprint: str,
) -> str:
    """Return deterministic lineage identity for one candidate ancestry."""
    payload = {
        "parent_model_version": parent_model_version,
        "experiment_fingerprint": experiment_fingerprint,
        "dataset_version": dataset_version,
        "artifact_fingerprint": artifact_fingerprint,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CandidateLifecycleController:
    """Create and advance immutable candidate lifecycle records."""

    def __init__(self, store: LearningStore | None = None) -> None:
        self.store = store

    def create(
        self,
        retraining: RetrainingResult,
        *,
        dataset_version: DatasetVersion,
        experiment: ExperimentSpec,
        candidate_id: str,
        candidate_version: str,
        parent_model_version: str,
        strategy_version: str,
        evaluation_fingerprint: str,
        metrics: Mapping[str, float],
        created_at: str,
        candidate_type: str | None = None,
    ) -> ModelCandidate:
        """Create and optionally persist a CANDIDATE from verified retraining."""
        if not isinstance(retraining, RetrainingResult):
            raise TypeError("retraining must be a RetrainingResult")
        if not isinstance(dataset_version, DatasetVersion):
            raise TypeError("dataset_version must be a DatasetVersion")
        if not isinstance(experiment, ExperimentSpec):
            raise TypeError("experiment must be an ExperimentSpec")
        if retraining.dataset_version != dataset_version.dataset_version:
            raise ValueError("retraining and dataset versions do not match")
        if retraining.experiment_fingerprint != experiment.fingerprint:
            raise ValueError("retraining and experiment fingerprints do not match")
        if len(evaluation_fingerprint) != 64:
            raise ValueError("evaluation_fingerprint must be SHA-256")
        if not candidate_id.strip() or not candidate_version.strip():
            raise ValueError("candidate_id and candidate_version are required")
        if not parent_model_version.strip():
            raise ValueError("parent_model_version is required")
        if not strategy_version.strip():
            raise ValueError("strategy_version is required")
        if not created_at.strip():
            raise ValueError("created_at is required")

        lineage_id = _lineage_id(
            parent_model_version=parent_model_version,
            experiment_fingerprint=experiment.fingerprint,
            dataset_version=dataset_version.dataset_version,
            artifact_fingerprint=retraining.artifact_fingerprint,
        )

        candidate = ModelCandidate(
            candidate_id=candidate_id.strip(),
            candidate_version=candidate_version.strip(),
            candidate_type=(candidate_type or retraining.model_family).strip(),
            lifecycle=CandidateLifecycle.CANDIDATE,
            dataset_version=dataset_version.dataset_version,
            feature_version=dataset_version.feature_schema_version,
            label_version=dataset_version.label_definition_version,
            source_experiment_id=experiment.experiment_id,
            source_experiment_fingerprint=experiment.fingerprint,
            artifact_fingerprint=retraining.artifact_fingerprint,
            evaluation_fingerprint=evaluation_fingerprint,
            lineage_id=lineage_id,
            metrics=metrics,
            parent_model_version=parent_model_version.strip(),
            strategy_version=strategy_version.strip(),
            created_at=created_at.strip(),
        )
        self._persist(candidate)
        return candidate

    def transition(
        self,
        candidate: ModelCandidate,
        target: CandidateLifecycle,
        *,
        at: str,
        reason: str = "",
    ) -> ModelCandidate:
        """Apply one explicitly allowed lifecycle transition."""
        if not isinstance(candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        if not isinstance(target, CandidateLifecycle):
            raise TypeError("target must be a CandidateLifecycle")
        if not at.strip():
            raise ValueError("transition timestamp is required")

        allowed = _ALLOWED_TRANSITIONS[candidate.lifecycle]
        if target not in allowed:
            raise ValueError(
                f"invalid candidate lifecycle transition: "
                f"{candidate.lifecycle.value}->{target.value}"
            )
        if target is CandidateLifecycle.REJECTED and not reason.strip():
            raise ValueError("rejection reason is required")
        if target is CandidateLifecycle.RETIRED and not reason.strip():
            raise ValueError("retirement reason is required")

        transitioned = replace(candidate, lifecycle=target)
        self._persist(transitioned)
        return transitioned

    def apply_promotion(
        self,
        candidate: ModelCandidate,
        decision: PromotionDecision,
    ) -> ModelCandidate:
        """Apply only an explicit PROMOTED decision to a reviewable candidate."""
        if not isinstance(candidate, ModelCandidate):
            raise TypeError("candidate must be a ModelCandidate")
        if not isinstance(decision, PromotionDecision):
            raise TypeError("decision must be a PromotionDecision")
        if decision.state is not PromotionState.PROMOTED:
            raise ValueError("promotion decision is not PROMOTED")
        if decision.candidate_id != candidate.candidate_id:
            raise ValueError("promotion decision candidate_id does not match")
        if decision.candidate_fingerprint != candidate.fingerprint:
            raise ValueError("promotion decision does not match candidate")
        if candidate.lifecycle is not CandidateLifecycle.PROMOTION_REVIEW:
            raise ValueError(
                "only PROMOTION_REVIEW candidates can receive a promotion decision"
            )

        promoted = replace(
            candidate,
            lifecycle=CandidateLifecycle.PROMOTED,
        )
        self._persist(promoted)
        return promoted

    def _persist(self, candidate: ModelCandidate) -> None:
        if self.store is not None:
            self.store.add_candidate(candidate)


def allowed_transitions(
    lifecycle: CandidateLifecycle,
) -> tuple[CandidateLifecycle, ...]:
    """Return the deterministic set of legal next states."""
    if not isinstance(lifecycle, CandidateLifecycle):
        raise TypeError("lifecycle must be a CandidateLifecycle")
    return tuple(sorted(_ALLOWED_TRANSITIONS[lifecycle], key=lambda item: item.value))


__all__ = ["CandidateLifecycleController", "allowed_transitions"]
