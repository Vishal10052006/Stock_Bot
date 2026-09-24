"""Champion/challenger and rollback safeguards.

This module manages research/governance state only. It cannot place orders,
change hard risk limits, or enable live execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
            raise ValueError("rollback target must differ from current model")
        if not self.reason.strip():
            raise ValueError("rollback reason must be non-empty")
        if len(self.source_promotion_review) != 64:
            raise ValueError("source_promotion_review must be SHA-256")

    @property
    def fingerprint(self) -> str:
        """Return a deterministic rollback identity."""
        import hashlib
        import json

        payload = {
            "from_model_version": self.from_model_version,
            "to_model_version": self.to_model_version,
            "reason": self.reason,
            "source_promotion_review": self.source_promotion_review,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()


class ChampionChallenger:
    """Verify and materialize explicit champion/challenger transitions."""

    @staticmethod
    def require_candidate(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Return a CANDIDATE record or fail closed."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.CANDIDATE.value:
            raise ValueError("challenger must be CANDIDATE")
        return record

    @staticmethod
    def require_approved(
        registry: ModelRegistry,
        model_version: str,
    ) -> ModelRegistryRecord:
        """Return an APPROVED registry record."""
        record = registry.get(model_version)
        if record.approval_status != ModelRegistryStatus.APPROVED.value:
            raise ValueError("model must be APPROVED")
        return record

    @staticmethod
    def review_is_consistent(
        review: PromotionReview,
        *,
        current_model_version: str,
        challenger_model_version: str,
    ) -> bool:
        """Verify that a review compares the expected pair."""
        if not isinstance(review, PromotionReview):
            raise TypeError("review must be a PromotionReview")
        if review.current_model_version != current_model_version:
            raise ValueError("review current model mismatch")
        if review.challenger_model_version != challenger_model_version:
            raise ValueError("review challenger model mismatch")
        return True

    @staticmethod
    def build_activation(
        review: PromotionReview,
        approved_model: ModelRegistryRecord,
        *,
        experiment_id: str,
        parent_model_version: str,
        activated_at: str | None = None,
    ) -> ChampionRecord:
        """Create an activation record after explicit governance approval."""
        if not review.promotable:
            raise ValueError("promotion review is not promotable")
        if approved_model.approval_status != ModelRegistryStatus.APPROVED.value:
            raise ValueError("approved_model must be APPROVED")
        if approved_model.model_version != review.challenger_model_version:
            raise ValueError("approved model does not match challenger")
        if not experiment_id.strip():
            raise ValueError("experiment_id must be non-empty")

        return ChampionRecord(
            model_version=approved_model.model_version,
            status="PROMOTED",
            activated_at=activated_at or datetime.now().astimezone().isoformat(),
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
    """Create a rollback plan without changing runtime state."""
    return RollbackPlan(
        from_model_version=current_model_version,
        to_model_version=previous_verified_version,
        reason=reason,
        source_promotion_review=promotion_review_fingerprint,
    )
