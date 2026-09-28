"""Tests for SL-25 validation evidence orchestration."""

import pytest

from self_learning.candidate_lifecycle import CandidateLifecycleController
from self_learning.contracts import CandidateLifecycle, ValidationSummary
from self_learning.validation_orchestrator import ValidationOrchestrator, ValidationRun

from tests.self_learning.test_candidate_lifecycle import _candidate


def _stage(stage: str, *, valid: bool = True, fingerprint: str = "c" * 64) -> ValidationSummary:
    return ValidationSummary(
        stage=stage,
        valid=valid,
        observations=10,
        metrics={"score": 0.5},
        issues=() if valid else ("stage failed",),
        artifact_fingerprints=(fingerprint, "d" * 64),
    )


def _all_stages() -> dict[str, ValidationSummary]:
    return {
        stage: _stage(stage)
        for stage in ("BACKTEST", "LEAKAGE_AUDIT", "OOS", "WALK_FORWARD", "PAPER")
    }


def test_start_moves_candidate_to_validating() -> None:
    controller = ValidationOrchestrator()
    candidate = _candidate()

    validating = controller.start(
        candidate,
        at="2026-09-24T11:00:00+05:30",
    )

    assert validating.lifecycle is CandidateLifecycle.VALIDATING


def test_collect_builds_immutable_validation_run() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(
        _candidate(),
        at="2026-09-24T11:00:00+05:30",
    )

    run = controller.collect(candidate, _all_stages())

    assert isinstance(run, ValidationRun)
    assert run.candidate_fingerprint == candidate.fingerprint
    assert tuple(run.stage_map) == (
        "BACKTEST",
        "LEAKAGE_AUDIT",
        "OOS",
        "WALK_FORWARD",
        "PAPER",
    )
    assert run.gate.valid is True
    assert len(run.gate.artifact_fingerprints) == 2


def test_collect_requires_stage_key_to_match_summary() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    validations = _all_stages()
    validations["OOS"] = _stage("BACKTEST")

    with pytest.raises(ValueError, match="does not match"):
        controller.collect(candidate, validations)


def test_collect_rejects_unknown_stage() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    validations = _all_stages()
    validations["CUSTOM"] = _stage("CUSTOM")

    with pytest.raises(ValueError, match="unknown validation stages"):
        controller.collect(candidate, validations)


def test_collect_preserves_missing_stage_as_gate_failure() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    validations = _all_stages()
    del validations["OOS"]

    run = controller.collect(candidate, validations)

    assert run.gate.valid is False
    assert "MISSING_STAGE:OOS" in run.gate.issues


def test_collect_rejects_invalid_stage_evidence() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    validations = _all_stages()
    validations["OOS"] = _stage("OOS", valid=False)

    run = controller.collect(candidate, validations)

    assert run.gate.valid is False
    assert "STAGE_INVALID:OOS" in run.gate.issues


def test_complete_requires_valid_gate() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    validations = _all_stages()
    validations["PAPER"] = _stage("PAPER", valid=False)
    run = controller.collect(candidate, validations)

    with pytest.raises(ValueError, match="gate is invalid"):
        controller.complete(candidate, run, at="2026-09-24T11:10:00+05:30")


def test_complete_requires_matching_candidate_fingerprint() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    run = controller.collect(candidate, _all_stages())
    changed = CandidateLifecycleController().transition(
        candidate,
        CandidateLifecycle.REJECTED,
        at="2026-09-24T11:05:00+05:30",
        reason="test",
    )

    with pytest.raises(ValueError, match="does not match candidate"):
        controller.complete(changed, run, at="2026-09-24T11:10:00+05:30")


def test_complete_advances_to_promotion_review() -> None:
    controller = ValidationOrchestrator()
    candidate = controller.start(_candidate(), at="2026-09-24T11:00:00+05:30")
    run = controller.collect(candidate, _all_stages())

    reviewable = controller.complete(
        candidate,
        run,
        at="2026-09-24T11:10:00+05:30",
    )

    assert reviewable.lifecycle is CandidateLifecycle.PROMOTION_REVIEW


def test_collect_requires_validating_lifecycle() -> None:
    controller = ValidationOrchestrator()

    with pytest.raises(ValueError, match="VALIDATING"):
        controller.collect(_candidate(), _all_stages())
