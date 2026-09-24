"""Champion/challenger promotion and rollback controller.

This controller is deliberately independent from Risk, Safety, Broker and
Execution.  Promotion is explicit and reversible; it is never inferred from
one metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .contracts import ModelCandidate, PromotionDecision, PromotionState, ValidationSummary
from .validation import validate_candidate, ValidationPolicy


@dataclass(frozen=True, slots=True)
class PromotionController:
    """Govern candidate review without modifying broker or risk state."""

    def review(
        self,
        *,
        champion_version: str,
        challenger: ModelCandidate,
        validations: dict[str, ValidationSummary],
        policy: ValidationPolicy | None = None,
    ) -> PromotionDecision:
        """Create a deterministic promotion-review decision.

        A structurally complete candidate becomes ELIGIBLE for explicit
        approval. It does not become production automatically.
        """
        gate = validate_candidate(challenger, validations, policy=policy)

        if not gate.valid:
            return PromotionDecision(
                candidate_id=challenger.candidate_id,
                candidate_fingerprint=challenger.fingerprint,
                champion_version=champion_version,
                challenger_version=challenger.candidate_version,
                state=PromotionState.BLOCKED,
                reasons=gate.issues,
                validation_fingerprints=tuple(
                    fingerprint for result in validations.values()
                    for fingerprint in result.artifact_fingerprints
                ),
            )

        return PromotionDecision(
            candidate_id=challenger.candidate_id,
            candidate_fingerprint=challenger.fingerprint,
            champion_version=champion_version,
            challenger_version=challenger.candidate_version,
            state=PromotionState.ELIGIBLE,
            reasons=("All required validation evidence is structurally present.",),
            validation_fingerprints=tuple(
                fingerprint for result in validations.values()
                for fingerprint in result.artifact_fingerprints
            ),
        )

    def approve(
        self,
        review: PromotionDecision,
        *,
        approval_reference: str,
        evaluator: str,
    ) -> PromotionDecision:
        """Record explicit human/governance approval of an eligible review."""
        if review.state is not PromotionState.ELIGIBLE:
            raise ValueError("only ELIGIBLE reviews can be promoted")
        if not approval_reference.strip() or not evaluator.strip():
            raise ValueError("approval_reference and evaluator are required")

        return PromotionDecision(
            candidate_id=review.candidate_id,
            candidate_fingerprint=review.candidate_fingerprint,
            champion_version=review.champion_version,
            challenger_version=review.challenger_version,
            state=PromotionState.PROMOTED,
            reasons=review.reasons,
            validation_fingerprints=review.validation_fingerprints,
            approval_reference=approval_reference.strip(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def rollback(
        self,
        *,
        candidate_id: str,
        candidate_fingerprint: str,
        current_version: str,
        previous_verified_version: str,
        reason: str,
    ) -> PromotionDecision:
        """Create a rollback record without retraining or executing trades."""
        if current_version.strip() == previous_verified_version.strip():
            raise ValueError("previous_verified_version must differ from current_version")
        if not reason.strip():
            raise ValueError("rollback reason is required")
        return PromotionDecision(
            candidate_id=candidate_id,
            candidate_fingerprint=candidate_fingerprint,
            champion_version=current_version,
            challenger_version=previous_verified_version,
            state=PromotionState.ROLLED_BACK,
            reasons=(reason.strip(),),
            validation_fingerprints=(),
        )


__all__ = ["PromotionController"]
