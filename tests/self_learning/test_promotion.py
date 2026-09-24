"""Tests for promotion and validation gates."""

import pytest
from dataclasses import replace

from self_learning.contracts import (
    CandidateLifecycle,
    ModelCandidate,
    ValidationSummary,
    CandidateLifecycle,
)
from self_learning.promotion import PromotionController
from self_learning.validation import validate_candidate
from self_learning.validation_orchestrator import ValidationRun


def _candidate() -> ModelCandidate:
    return ModelCandidate(
        candidate_id="C1",
        candidate_version="model-v2",
        candidate_type="logistic_regression",
        lifecycle=CandidateLifecycle.CANDIDATE,
        dataset_version="dataset-v1",
        feature_version="features-v1",
        label_version="labels-v1",
        source_experiment_id="EXP-1",
        source_experiment_fingerprint="a" * 64,
        artifact_fingerprint="b" * 64,
        evaluation_fingerprint="c" * 64,
        lineage_id="d" * 64,
        metrics={"balanced_accuracy": 0.55, "log_loss": 0.95},
        parent_model_version="model-v1",
        strategy_version="strategy-v1",
        created_at="2026-09-24T10:00:00+05:30",
    )


def _validations(candidate: ModelCandidate):
    stages = ("BACKTEST", "LEAKAGE_AUDIT", "OOS", "WALK_FORWARD", "PAPER")
    result = {}
    for stage in stages:
        artifacts = [candidate.artifact_fingerprint]
        if stage == "OOS":
            artifacts.append(candidate.evaluation_fingerprint)
        result[stage] = ValidationSummary(
            stage=stage,
            valid=True,
            observations=10,
            metrics={"metric": 1.0},
            artifact_fingerprints=tuple(dict.fromkeys(artifacts)),
        )
    return result


def test_complete_evidence_is_eligible_but_not_promoted() -> None:
    candidate = _candidate()
    decision = PromotionController().review(
        champion_version="model-v1",
        challenger=candidate,
        validations=_validations(candidate),
    )
    assert decision.state.value == "ELIGIBLE"


def test_missing_stage_blocks_promotion_review() -> None:
    candidate = _candidate()
    validations = _validations(candidate)
    validations.pop("PAPER")

    gate = validate_candidate(candidate, validations)
    assert not gate.valid
    assert "MISSING_STAGE:PAPER" in gate.issues


def test_explicit_approval_is_required() -> None:
    candidate = _candidate()
    review = PromotionController().review(
        champion_version="model-v1",
        challenger=candidate,
        validations=_validations(candidate),
    )

    promoted = PromotionController().approve(
        review,
        approval_reference="review-001",
        evaluator="controlled-review",
    )
    assert promoted.state.value == "PROMOTED"


def test_blocked_review_cannot_be_approved() -> None:
    candidate = _candidate()
    validations = _validations(candidate)
    validations.pop("OOS")
    review = PromotionController().review(
        champion_version="model-v1",
        challenger=candidate,
        validations=validations,
    )

    with pytest.raises(ValueError, match="ELIGIBLE"):
        PromotionController().approve(
            review,
            approval_reference="review-002",
            evaluator="controlled-review",
        )


def test_rollback_requires_distinct_versions() -> None:
    with pytest.raises(ValueError, match="must differ"):
        PromotionController().rollback(
            candidate_id="C1",
            candidate_fingerprint="a" * 64,
            current_version="v1",
            previous_verified_version="v1",
            reason="incident",
        )


def test_rollback_is_explicit_and_non_execution() -> None:
    result = PromotionController().rollback(
        candidate_id="C1",
        candidate_fingerprint="a" * 64,
        current_version="v2",
        previous_verified_version="v1",
        reason="validated degradation",
    )
    assert result.state.value == "ROLLED_BACK"
    assert result.challenger_version == "v1"


def _validation_run(candidate: ModelCandidate) -> ValidationRun:
    validations = _validations(candidate)
    return ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )


def test_review_run_requires_exact_candidate_and_promotion_review_state() -> None:
    candidate = _candidate()
    run = _validation_run(candidate)

    with pytest.raises(ValueError, match="PROMOTION_REVIEW"):
        PromotionController().review_run(
            champion_version="model-v1",
            challenger=candidate,
            validation_run=run,
        )

    review_candidate = replace(candidate, lifecycle=CandidateLifecycle.PROMOTION_REVIEW)
    with pytest.raises(ValueError, match="does not match challenger"):
        PromotionController().review_run(
            champion_version="model-v1",
            challenger=review_candidate,
            validation_run=run,
        )


def test_review_run_binds_validation_run_fingerprint_to_decision() -> None:
    candidate = replace(_candidate(), lifecycle=CandidateLifecycle.PROMOTION_REVIEW)
    run = _validation_run(candidate)

    decision = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )

    assert decision.state.value == "ELIGIBLE"
    assert run.fingerprint in decision.validation_fingerprints


def test_review_run_revalidates_stage_evidence() -> None:
    candidate = replace(_candidate(), lifecycle=CandidateLifecycle.PROMOTION_REVIEW)
    validations = _validations(candidate)
    validations["PAPER"] = replace(validations["PAPER"], valid=False, issues=("PAPER_FAILED",))
    run = ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )

    decision = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )

    assert decision.state.value == "BLOCKED"
    assert "STAGE_INVALID:PAPER" in decision.reasons
