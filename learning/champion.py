"""Champion selection and rollback safeguards.

This module deliberately stops short of broker/live authority. It manages
research/governance state only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ml.model_registry import ModelRegistry, ModelRegistryRecord, ModelRegistryStatus

from .self_learning_models import ChampionRecord, PromotionReview


@dataclass(frozen=True, slots=True)
class RollbackPlan:
    """Immutable, auditable rollback plan."""

    from_model_version: str
    to_model_version: str
    reason: str
    source_promotion_review: str

    def __post_init__(self) -> None:
        if not self.from_model_version.strip() or not self.to_model_version.strip():
            raise ValueError("model versions must be non-empty")
        if self.from_model_version == self.to_model_version:
            raise ValueError("rollback must change the active model version")
        if not self.reason.strip():
            raise ValueError("rollback reason must be non-empty")
        if len(self.source_promotion_review) != 64:
            raise ValueError("source_promotion_review must be SHA-256")


class ChampionChallenger:
    """Compare an already-evaluated challenger with the current champion.

    Quantitative selection policy is intentionally supplied by the caller.
    This component verifies identity/provenance and prevents an unapproved
    candidate from becoming a champion.
    """

    @staticmethod
    def require_candidate(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Return a candidate model or fail closed."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.CANDIDATE.value:
            raise ValueError("challenger must be registered as CANDIDATE")
        return record

    @staticmethod
    def require_approved(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Return an approved model for champion activation."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.APPROVED.value:
            raise ValueError("champion must reference an APPROVED model")
        return record

    @staticmethod
    def review_is_consistent(
        review: PromotionReview,
        *,
        current_model_version: str,
        challenger_model_version: str,
    ) -> bool:
        """Validate that a promotion review compares the intended pair."""
        if not isinstance(review, PromotionReview):
            raise TypeError("review must be a PromotionReview")
        return (
            review.current_model_version == current_model_version
            and review.challenger_model_version == challenger_model_version
        )


def build_rollback_plan(
    *,
    current_model_version: str,
    previous_verified_version: str,
    reason: str,
    promotion_review_fingerprint: str,
) -> RollbackPlan:
    """Build a rollback plan without changing any registry or runtime state."""
    return RollbackPlan(
        from_model_version=current_model_version,
        to_model_version=previous_verified_version,
        reason=reason,
        source_promotion_review=promotion_review_fingerprint,
    )
