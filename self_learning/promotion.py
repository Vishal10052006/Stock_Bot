"""Champion/challenger promotion and rollback controller.

This controller is independent from risk, safety, and execution. Promotion is
explicit and reversible; it is never inferred from one metric.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .contracts import ModelCandidate, PromotionDecision, PromotionState, ValidationSummary
from .validation import validate_candidate, ValidationPolicy


class PromotionController:
    """Govern candidate review without trading execution authority."""

    def review(
        self,
        *,
        champion_version: str,
        challenger: ModelCandidate,
        validations: dict[str, ValidationSummary],
        policy: ValidationPolicy | None = None,
    ) -> PromotionDecision:
        """Create a deterministic promotion-review decision."""
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
                    fingerprint
                    for result in validations.values()
                    for fingerprint in result.artifact_fingerprints
                ),
            )

        return PromotionDecision(
            candidate_id=challenger.candidate_id,
            candidate_fingerprint=challenger.fingerprint,
            champion_version=champion_version,
            challenger_version=challenger.candidate_version,
            state=PromotionState.ELIGIBLE,
            reasons=("Required validation evidence is structurally present.",),
            validation_fingerprints=tuple(
                fingerprint
                for result in validations.values()
                for fingerprint in result.artifact_fingerprints
            ),
        )

    def review_run(
        self,
        *,
        champion_version: str,
        challenger: ModelCandidate,
        validation_run: "ValidationRun",
        policy: ValidationPolicy | None = None,
    ) -> PromotionDecision:
        """Review one immutable validation run bound to this exact candidate.

        The run identity is included in the decision evidence so a promotion
        review cannot be detached from the validation bundle that produced it.
        """
        from .validation_orchestrator import ValidationRun

        if not isinstance(validation_run, ValidationRun):
            raise TypeError("validation_run must be a ValidationRun")
        if challenger.lifecycle.value != "PROMOTION_REVIEW":
            raise ValueError("candidate must be PROMOTION_REVIEW before promotion review")
        if validation_run.candidate_fingerprint != challenger.fingerprint:
            raise ValueError("validation run does not match challenger")

        gate = validate_candidate(
            challenger,
            dict(validation_run.stage_map),
            policy=policy,
        )
        evidence = tuple(
            fingerprint
            for result in validation_run.stages
            for fingerprint in result.artifact_fingerprints
        ) + (validation_run.fingerprint,)

        if not gate.valid:
            return PromotionDecision(
                candidate_id=challenger.candidate_id,
                candidate_fingerprint=challenger.fingerprint,
                champion_version=champion_version,
                challenger_version=challenger.candidate_version,
                state=PromotionState.BLOCKED,
                reasons=gate.issues,
                validation_fingerprints=tuple(dict.fromkeys(evidence)),
            )

        return PromotionDecision(
            candidate_id=challenger.candidate_id,
            candidate_fingerprint=challenger.fingerprint,
            champion_version=champion_version,
            challenger_version=challenger.candidate_version,
            state=PromotionState.ELIGIBLE,
            reasons=("Required validation evidence is structurally present.",),
            validation_fingerprints=tuple(dict.fromkeys(evidence)),
        )

    def approve(
        self,
        review: PromotionDecision,
        *,
        approval_reference: str,
        evaluator: str,
    ) -> PromotionDecision:
        """Record explicit governance approval of an eligible review."""
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
            reasons=review.reasons + (f"Approved by {evaluator.strip()}.",),
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
        """Create a rollback record without retraining or execution."""
        if current_version.strip() == previous_verified_version.strip():
            raise ValueError("previous_verified_version must differ from current_version")
        if len(candidate_fingerprint) != 64:
            raise ValueError("candidate_fingerprint must be SHA-256")
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
