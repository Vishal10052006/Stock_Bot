"""Safe model-promotion and rollback helpers.

This module connects the learning governance contracts to the existing model
registry, but never places orders or changes broker/runtime authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ml.model_registry import ModelRegistry, ModelRegistryRecord, ModelRegistryStatus

from .self_learning_models import ChampionRecord, PromotionReview


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    """Immutable plan for returning to a previously verified model."""

    from_model_version: str
    to_model_version: str
    reason: str
    source_promotion_review: str

    def __post_init__(self) -> None:
        if not self.from_model_version.strip() or not self.to_model_version.strip():
            raise ValueError("model versions must be non-empty")
        if self.from_model_version == self.to_model_version:
            raise ValueError("rollback target must differ from current model")
        if not self.reason.strip():
            raise ValueError("rollback reason must be non-empty")
        if len(self.source_promotion_review) != 64:
            raise ValueError("source_promotion_review must be SHA-256")


class ChampionChallenger:
    """Provenance checks and explicit champion activation boundary."""

    @staticmethod
    def require_candidate(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Require that a challenger is still a registered candidate."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.CANDIDATE.value:
            raise ValueError("challenger must be CANDIDATE")
        return record

    @staticmethod
    def require_approved(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Require that a champion points to an approved registry version."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.APPROVED.value:
            raise ValueError("champion must be APPROVED")
        return record

    @staticmethod
    def review_is_consistent(
        review: PromotionReview,
        *,
        current_model_version: str,
        challenger_model_version: str,
    ) -> bool:
        """Verify that a promotion review compares the intended pair."""
        if not isinstance(review, PromotionReview):
            raise TypeError("review must be a PromotionReview")
        return (
            review.current_model_version == current_model_version
            and review.challenger_model_version == challenger_model_version
        )

    @staticmethod
    def build_activation(
        review: PromotionReview,
        approved_model: ModelRegistryRecord,
        *,
        experiment_id: str,
        activated_at: str | None = None,
        parent_model_version: str,
    ) -> ChampionRecord:
        """Create an activation record after explicit registry approval."""
        if not review.promotable:
            raise ValueError("promotion review is not promotable")
        if approved_model.approval_status != ModelRegistryStatus.APPROVED.value:
            raise ValueError("approved_model must have APPROVED registry status")
        if approved_model.model_version != review.challenger_model_version:
            raise ValueError("approved model does not match challenger")
        if not experiment_id.strip():
            raise ValueError("experiment_id must be non-empty")

        timestamp = activated_at or datetime.now().astimezone().isoformat()
        return ChampionRecord(
            model_version=approved_model.model_version,
            status="PROMOTED",
            activated_at=timestamp,
            experiment_id=experiment_id,
            promotion_review_fingerprint=review.fingerprint,
            parent_model_version=parent_model_version,
        )


def build_rollback_plan(
    *,
    current_model_version: str,
    previous_verified_version: str,
    reason: str,
    promotion_review_fingerprint: str,
) -> RollbackPlan:
    """Create a rollback plan without mutating the registry."""
    return RollbackPlan(
        from_model_version=current_model_version,
        to_model_version=previous_verified_version,
        reason=reason,
        source_promotion_review=promotion_review_fingerprint,
    )


def apply_rollback(
    champion_store: object,
    *,
    current_model_version: str,
    previous_verified_version: str,
    review: PromotionReview,
    reason: str,
    experiment_id: str,
    rollback_id: str,
    timestamp: str | None = None,
) -> object:
    """Record a rollback activation against the existing ChampionStore.

    The model registry is not modified here. Runtime/model loading remains the
    responsibility of the model-serving layer.
    """
    from .lifecycle import RollbackRecord

    if not isinstance(review, PromotionReview):
        raise TypeError("review must be a PromotionReview")

    plan = build_rollback_plan(
        current_model_version=current_model_version,
        previous_verified_version=previous_verified_version,
        reason=reason,
        promotion_review_fingerprint=review.fingerprint,
    )
    if review.challenger_model_version != current_model_version:
        raise ValueError("review challenger must match current model for rollback")

    rollback = RollbackRecord(
        rollback_id=rollback_id,
        from_model_version=plan.from_model_version,
        to_model_version=plan.to_model_version,
        reason=plan.reason,
        timestamp=timestamp or datetime.now().astimezone().isoformat(),
        review_fingerprint=review.fingerprint,
    )
    return rollback
