"""Controlled promotion gate for the self-learning engine.

A candidate is promotable only after integrity, leakage, OOS, walk-forward,
paper, reproducibility, and explicit governance approval all pass. The gate
does not execute or enable live trading.

References:
    STOCK_BOT self-learning master specification.
    Existing ml.model_registry.ModelRegistry.
"""

from __future__ import annotations

from dataclasses import dataclass

from ml.model_registry import (
    ModelApproval,
    ModelRegistry,
    ModelRegistryRecord,
    ModelRegistryStatus,
)

from .self_learning_models import LearningDecision, PromotionReview, ValidationEvidence


@dataclass(frozen=True, slots=True)
class PromotionGate:
    """Create immutable promotion reviews and apply explicit approval evidence."""

    require_governance_approval: bool = True

    def review(
        self,
        *,
        candidate_id: str,
        candidate_fingerprint: str,
        current_model_version: str,
        challenger_model_version: str,
        validation: ValidationEvidence,
        reproducibility_passed: bool,
        governance_approved: bool = False,
        decision: LearningDecision | None = None,
    ) -> PromotionReview:
        """Evaluate every mandatory gate without mutating registry/runtime state."""
        if not isinstance(validation, ValidationEvidence):
            raise TypeError("validation must be a ValidationEvidence")
        reasons: list[str] = []

        if not validation.integrity_passed:
            reasons.append("INTEGRITY_GATE_FAILED")
        if not validation.leakage_passed:
            reasons.append("LEAKAGE_GATE_FAILED")
        if not validation.oos_passed:
            reasons.append("OOS_GATE_FAILED")
        if not validation.walk_forward_passed:
            reasons.append("WALK_FORWARD_GATE_FAILED")
        if not validation.paper_passed:
            reasons.append("PAPER_GATE_FAILED")
        if not reproducibility_passed:
            reasons.append("REPRODUCIBILITY_GATE_FAILED")
        if validation.issues:
            reasons.extend(f"EVIDENCE_ISSUE:{issue}" for issue in validation.issues)
        if self.require_governance_approval and not governance_approved:
            reasons.append("GOVERNANCE_APPROVAL_REQUIRED")

        final_decision = (
            decision
            if decision is not None
            else (LearningDecision.KEEP if not reasons else LearningDecision.REJECT)
        )
        if final_decision is LearningDecision.KEEP and reasons:
            final_decision = LearningDecision.REJECT

        return PromotionReview(
            candidate_id=candidate_id,
            candidate_fingerprint=candidate_fingerprint,
            current_model_version=current_model_version,
            challenger_model_version=challenger_model_version,
            validation=validation,
            reproducibility_passed=reproducibility_passed,
            governance_approved=governance_approved,
            decision=final_decision,
            reasons=tuple(reasons),
        )

    def approve_into_registry(
        self,
        registry: ModelRegistry,
        *,
        challenger_model_version: str,
        approval: ModelApproval,
    ) -> ModelRegistryRecord:
        """Apply already-explicit governance evidence to a CANDIDATE model."""
        if not isinstance(registry, ModelRegistry):
            raise TypeError("registry must be a ModelRegistry")
        if not isinstance(approval, ModelApproval):
            raise TypeError("approval must be a ModelApproval")
        record = registry.get(challenger_model_version)
        if record.approval_status != ModelRegistryStatus.CANDIDATE.value:
            raise ValueError("challenger must be registered as CANDIDATE")
        return registry.approve(challenger_model_version, approval)
