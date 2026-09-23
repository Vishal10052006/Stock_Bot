"""S28 controlled self-learning proposal boundary."""

from __future__ import annotations

from dataclasses import dataclass

from .definition import ExperimentDefinition
from .evaluation import EvaluationReport
from .record import ExperimentRecord


@dataclass(frozen=True, slots=True)
class LearningProposal:
    """Immutable proposed research change; never an automatic configuration mutation."""

    proposal_id: str
    source_experiment_fingerprint: str
    requested_changes: tuple[tuple[str, str], ...]
    rationale: str

    def __post_init__(self) -> None:
        if not self.proposal_id.strip():
            raise ValueError("proposal_id must not be empty")
        if len(self.source_experiment_fingerprint) != 64:
            raise ValueError("source_experiment_fingerprint must be SHA-256")
        if not self.requested_changes:
            raise ValueError("requested_changes must not be empty")
        if not self.rationale.strip():
            raise ValueError("rationale must not be empty")

        keys = [key for key, _ in self.requested_changes]
        if len(keys) != len(set(keys)):
            raise ValueError("requested change keys must be unique")


@dataclass(frozen=True, slots=True)
class LearningGateResult:
    """Validation result for a proposed learning change."""

    proposal_id: str
    status: str
    reasons: tuple[str, ...]

    @property
    def can_change_frozen_configuration(self) -> bool:
        return False


def validate_learning_proposal(
    proposal: LearningProposal,
    definition: ExperimentDefinition,
    record: ExperimentRecord,
    evaluation: EvaluationReport,
) -> LearningGateResult:
    """Check whether a proposal is eligible for a future validation experiment.

    Even a fully valid proposal remains a proposal. This function never
    mutates strategy/model configuration and never performs promotion.
    """
    for obj, name in (
        (proposal, "proposal"),
        (definition, "definition"),
        (record, "record"),
        (evaluation, "evaluation"),
    ):
        if not isinstance(obj, {
            "proposal": LearningProposal,
            "definition": ExperimentDefinition,
            "record": ExperimentRecord,
            "evaluation": EvaluationReport,
        }[name]):
            raise TypeError(f"{name} has invalid type")

    reasons: list[str] = []

    if proposal.source_experiment_fingerprint != definition.fingerprint():
        reasons.append("SOURCE_EXPERIMENT_MISMATCH")
    if record.definition_fingerprint != definition.fingerprint():
        reasons.append("RECORD_DEFINITION_MISMATCH")
    if not evaluation.valid:
        reasons.append("EVALUATION_INVALID")

    allowed = set(definition.allowed_change)
    for key, _ in proposal.requested_changes:
        if key not in allowed:
            reasons.append(f"CHANGE_NOT_ALLOWED:{key}")

    if record.decision == "REJECT":
        reasons.append("SOURCE_EXPERIMENT_REJECTED")

    if reasons:
        return LearningGateResult(
            proposal_id=proposal.proposal_id,
            status="BLOCKED",
            reasons=tuple(reasons),
        )

    return LearningGateResult(
        proposal_id=proposal.proposal_id,
        status="VALIDATION_REQUIRED",
        reasons=(
            "Proposal is eligible only to start a new frozen validation experiment.",
        ),
    )
