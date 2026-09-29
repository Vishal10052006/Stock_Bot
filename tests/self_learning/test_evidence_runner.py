"""Tests for the fail-closed evidence-cycle bundle boundary."""

from dataclasses import replace

import pytest

from self_learning.contracts import CandidateLifecycle, ValidationSummary
from self_learning.evidence_runner import (
    REQUIRED_STAGES,
    EvidenceBundle,
    build_evidence_bundle,
)
from self_learning.promotion import PromotionController
from self_learning.validation import validate_candidate
from self_learning.validation_orchestrator import ValidationRun

from tests.self_learning.test_candidate_lifecycle import _candidate


def _validations(candidate):
    result = {}
    for stage in REQUIRED_STAGES:
        artifacts = [candidate.artifact_fingerprint]
        if stage == "OOS":
            artifacts.append(candidate.evaluation_fingerprint)
        result[stage] = ValidationSummary(
            stage=stage,
            valid=True,
            observations=10,
            metrics={"score": 1.0},
            artifact_fingerprints=tuple(dict.fromkeys(artifacts)),
        )
    return result


def _ready_candidate_and_run():
    candidate = _candidate()
    candidate = replace(candidate, lifecycle=CandidateLifecycle.PROMOTION_REVIEW)
    validations = _validations(candidate)
    run = ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )
    review = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )
    return candidate, run, review


def test_complete_bundle_binds_candidate_run_and_review():
    candidate, run, review = _ready_candidate_and_run()
    bundle = build_evidence_bundle(candidate, run, review)

    assert isinstance(bundle, EvidenceBundle)
    assert tuple(stage.stage for stage in bundle.stages) == REQUIRED_STAGES
    assert bundle.candidate_fingerprint == candidate.fingerprint
    assert bundle.validation_run_fingerprint == run.fingerprint
    assert bundle.promotion_review.state.value == "ELIGIBLE"
    assert len(bundle.fingerprint) == 64


def test_missing_stage_cannot_be_packaged():
    candidate = _candidate()
    candidate = replace(candidate, lifecycle=CandidateLifecycle.PROMOTION_REVIEW)
    validations = _validations(candidate)
    validations.pop("PAPER")
    run = ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )
    review = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )

    with pytest.raises(ValueError, match="missing required evidence"):
        build_evidence_bundle(candidate, run, review)


def test_invalid_stage_cannot_be_packaged():
    candidate, _, _ = _ready_candidate_and_run()
    validations = _validations(candidate)
    validations["PAPER"] = replace(
        validations["PAPER"],
        valid=False,
        issues=("PAPER_FAILED",),
    )
    run = ValidationRun(
        candidate_fingerprint=candidate.fingerprint,
        stages=tuple(validations.values()),
        gate=validate_candidate(candidate, validations),
    )
    review = PromotionController().review_run(
        champion_version="model-v1",
        challenger=candidate,
        validation_run=run,
    )

    with pytest.raises(ValueError, match="invalid stages"):
        build_evidence_bundle(candidate, run, review)


def test_mismatched_candidate_is_rejected():
    candidate, run, review = _ready_candidate_and_run()
    other = _candidate()

    with pytest.raises(ValueError, match="does not match candidate"):
        build_evidence_bundle(other, run, review)


def test_blocked_review_is_not_a_complete_bundle():
    candidate, run, _ = _ready_candidate_and_run()
    blocked = PromotionController().review(
        champion_version="model-v1",
        challenger=candidate,
        validations={},
    )

    with pytest.raises(ValueError, match="promotion review is blocked"):
        build_evidence_bundle(candidate, run, blocked)
