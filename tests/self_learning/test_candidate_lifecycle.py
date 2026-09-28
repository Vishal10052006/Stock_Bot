"""Tests for the SL-24 candidate lifecycle controller."""

from pathlib import Path

import pytest

from self_learning.candidate_lifecycle import (
    CandidateLifecycleController,
    allowed_transitions,
)
from self_learning.contracts import (
    CandidateLifecycle,
    DatasetVersion,
    ExperimentSpec,
    ModelCandidate,
    PromotionDecision,
    PromotionState,
)
from self_learning.retraining import RetrainingResult
from self_learning.store import LearningStore


def _dataset_version() -> DatasetVersion:
    return DatasetVersion(
        dataset_version="dataset-v1",
        source="phase9.parquet",
        creation_timestamp="2026-09-24T10:00:00+05:30",
        symbols=("AAA",),
        period_start="2026-01-01T09:15:00",
        period_end="2026-01-02T05:10:00",
        row_count=480,
        label_distribution={"LONG_SUCCESS": 160, "SHORT_SUCCESS": 160, "NO_EDGE": 160},
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
        source_fingerprints=("a" * 64,),
    )


def _experiment() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="EXP-SL24",
        research_question="Does controlled lifecycle preserve candidate lineage?",
        hypothesis="Candidate provenance remains immutable.",
        null_hypothesis="Candidate provenance can be detached.",
        failure_criterion="Reject on provenance mismatch.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        feature_version="phase9-features-v1",
        label_version="phase9-labels-v1",
        model_version="model-v1",
        strategy_version="strategy-v1",
        risk_version="risk-v1",
        execution_version="execution-v1",
        period_start="2026-01-01T09:15:00",
        period_end="2026-01-02T05:10:00",
        symbols=("AAA",),
        method="controlled-lifecycle",
        changed_component="model",
        changed_parameter="trainer",
        baseline_fingerprints={"baseline": "b" * 64},
    )


def _retraining(experiment: ExperimentSpec) -> RetrainingResult:
    from types import SimpleNamespace

    result = SimpleNamespace(
        model=object(),
        preprocessor=object(),
        calibrator=object(),
    )
    # RetrainingResult requires a TrainingResult, so use the minimal
    # production-shaped object already accepted by the immutable contract.
    from ml.training.models import TrainingResult
    import pandas as pd

    probabilities = pd.DataFrame(
        {
            "LONG_SUCCESS": [0.6],
            "SHORT_SUCCESS": [0.2],
            "NO_EDGE": [0.2],
        }
    )
    training = TrainingResult(
        train_rows=10,
        calibration_rows=2,
        validation_rows=1,
        test_rows=1,
        train_end=pd.Timestamp("2026-01-01 10:00"),
        validation_start=pd.Timestamp("2026-01-01 10:05"),
        validation_end=pd.Timestamp("2026-01-01 10:10"),
        test_start=pd.Timestamp("2026-01-01 10:15"),
        validation_probabilities=probabilities,
        preprocessor=object(),
        model=object(),
        calibrator=object(),
    )
    return RetrainingResult(
        model_family="logistic_regression",
        result=training,
        dataset_version=experiment.dataset_version,
        experiment_fingerprint=experiment.fingerprint,
        artifact_fingerprint="c" * 64,
    )


def _candidate() -> ModelCandidate:
    dataset = _dataset_version()
    experiment = _experiment()
    return CandidateLifecycleController().create(
        _retraining(experiment),
        dataset_version=dataset,
        experiment=experiment,
        candidate_id="CAND-1",
        candidate_version="candidate-v1",
        parent_model_version="model-v1",
        strategy_version="strategy-v1",
        evaluation_fingerprint="d" * 64,
        metrics={"balanced_accuracy": 0.55},
        created_at="2026-09-24T10:00:00+05:30",
    )


def test_create_binds_retraining_provenance() -> None:
    candidate = _candidate()

    assert candidate.lifecycle is CandidateLifecycle.CANDIDATE
    assert candidate.source_experiment_id == "EXP-SL24"
    assert candidate.dataset_version == "dataset-v1"
    assert candidate.artifact_fingerprint == "c" * 64
    assert len(candidate.lineage_id) == 64


def test_lineage_is_deterministic() -> None:
    first = _candidate()
    second = _candidate()
    assert first.lineage_id == second.lineage_id
    assert first.fingerprint == second.fingerprint


def test_provenance_mismatch_is_rejected() -> None:
    experiment = _experiment()
    retraining = _retraining(experiment)
    other = _dataset_version()
    object.__setattr__(other, "dataset_version", "other")

    with pytest.raises(ValueError, match="dataset versions"):
        CandidateLifecycleController().create(
            retraining,
            dataset_version=other,
            experiment=experiment,
            candidate_id="CAND-1",
            candidate_version="candidate-v1",
            parent_model_version="model-v1",
            strategy_version="strategy-v1",
            evaluation_fingerprint="d" * 64,
            metrics={"balanced_accuracy": 0.55},
            created_at="2026-09-24T10:00:00+05:30",
        )


def test_experiment_fingerprint_mismatch_is_rejected() -> None:
    experiment = _experiment()
    retraining = _retraining(experiment)
    other = _experiment()
    object.__setattr__(other, "experiment_id", "EXP-OTHER")

    with pytest.raises(ValueError, match="experiment fingerprints"):
        CandidateLifecycleController().create(
            retraining,
            dataset_version=_dataset_version(),
            experiment=other,
            candidate_id="CAND-1",
            candidate_version="candidate-v1",
            parent_model_version="model-v1",
            strategy_version="strategy-v1",
            evaluation_fingerprint="d" * 64,
            metrics={"balanced_accuracy": 0.55},
            created_at="2026-09-24T10:00:00+05:30",
        )


def test_valid_lifecycle_path() -> None:
    controller = CandidateLifecycleController()
    candidate = _candidate()
    validating = controller.transition(
        candidate, CandidateLifecycle.VALIDATING, at="2026-09-24T10:01:00+05:30"
    )
    paper = controller.transition(
        validating, CandidateLifecycle.PAPER, at="2026-09-24T10:02:00+05:30"
    )
    review = controller.transition(
        paper, CandidateLifecycle.PROMOTION_REVIEW, at="2026-09-24T10:03:00+05:30"
    )

    assert review.lifecycle is CandidateLifecycle.PROMOTION_REVIEW


def test_invalid_direct_promotion_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid candidate lifecycle transition"):
        CandidateLifecycleController().transition(
            _candidate(),
            CandidateLifecycle.PROMOTED,
            at="2026-09-24T10:01:00+05:30",
        )


def test_rejection_requires_reason() -> None:
    with pytest.raises(ValueError, match="rejection reason"):
        CandidateLifecycleController().transition(
            _candidate(),
            CandidateLifecycle.REJECTED,
            at="2026-09-24T10:01:00+05:30",
        )


def test_promotion_requires_matching_explicit_decision() -> None:
    controller = CandidateLifecycleController()
    candidate = _candidate()
    candidate = controller.transition(
        candidate, CandidateLifecycle.VALIDATING, at="2026-09-24T10:01:00+05:30"
    )
    candidate = controller.transition(
        candidate, CandidateLifecycle.PAPER, at="2026-09-24T10:02:00+05:30"
    )
    candidate = controller.transition(
        candidate, CandidateLifecycle.PROMOTION_REVIEW, at="2026-09-24T10:03:00+05:30"
    )

    decision = PromotionDecision(
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.fingerprint,
        champion_version="model-v1",
        challenger_version=candidate.candidate_version,
        state=PromotionState.PROMOTED,
        reasons=("explicit approval",),
        validation_fingerprints=(candidate.evaluation_fingerprint,),
        approval_reference="approval-1",
        created_at="2026-09-24T10:04:00+05:30",
    )
    promoted = controller.apply_promotion(candidate, decision)
    assert promoted.lifecycle is CandidateLifecycle.PROMOTED


def test_promotion_decision_cannot_be_replayed_against_changed_candidate() -> None:
    controller = CandidateLifecycleController()
    candidate = _candidate()
    candidate = controller.transition(
        candidate, CandidateLifecycle.VALIDATING, at="2026-09-24T10:01:00+05:30"
    )
    candidate = controller.transition(
        candidate, CandidateLifecycle.PAPER, at="2026-09-24T10:02:00+05:30"
    )
    candidate = controller.transition(
        candidate, CandidateLifecycle.PROMOTION_REVIEW, at="2026-09-24T10:03:00+05:30"
    )
    decision = PromotionDecision(
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.fingerprint,
        champion_version="model-v1",
        challenger_version=candidate.candidate_version,
        state=PromotionState.PROMOTED,
        reasons=("explicit approval",),
        validation_fingerprints=(candidate.evaluation_fingerprint,),
        approval_reference="approval-1",
        created_at="2026-09-24T10:04:00+05:30",
    )
    promoted = controller.apply_promotion(candidate, decision)

    with pytest.raises(ValueError, match="PROMOTION_REVIEW"):
        controller.apply_promotion(promoted, decision)


def test_rejected_and_retired_are_terminal() -> None:
    controller = CandidateLifecycleController()
    rejected = controller.transition(
        _candidate(),
        CandidateLifecycle.REJECTED,
        at="2026-09-24T10:01:00+05:30",
        reason="failed validation",
    )
    assert allowed_transitions(rejected.lifecycle) == ()

    candidate = _candidate()
    candidate = controller.transition(candidate, CandidateLifecycle.VALIDATING, at="2026-09-24T10:01:00+05:30")
    candidate = controller.transition(candidate, CandidateLifecycle.PAPER, at="2026-09-24T10:02:00+05:30")
    candidate = controller.transition(candidate, CandidateLifecycle.PROMOTION_REVIEW, at="2026-09-24T10:03:00+05:30")
    decision = PromotionDecision(
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.fingerprint,
        champion_version="model-v1",
        challenger_version=candidate.candidate_version,
        state=PromotionState.PROMOTED,
        reasons=("explicit approval",),
        validation_fingerprints=(candidate.evaluation_fingerprint,),
        approval_reference="approval-1",
        created_at="2026-09-24T10:04:00+05:30",
    )
    promoted = controller.apply_promotion(candidate, decision)
    retired = controller.transition(
        promoted,
        CandidateLifecycle.RETIRED,
        at="2026-09-24T10:05:00+05:30",
        reason="superseded",
    )
    assert retired.lifecycle is CandidateLifecycle.RETIRED
    assert allowed_transitions(retired.lifecycle) == ()


def test_store_persists_each_immutable_lifecycle_state(tmp_path: Path) -> None:
    store = LearningStore(tmp_path / "learning.jsonl")
    controller = CandidateLifecycleController(store)
    candidate = controller.create(
        _retraining(_experiment()),
        dataset_version=_dataset_version(),
        experiment=_experiment(),
        candidate_id="CAND-STORE",
        candidate_version="candidate-v1",
        parent_model_version="model-v1",
        strategy_version="strategy-v1",
        evaluation_fingerprint="d" * 64,
        metrics={"balanced_accuracy": 0.55},
        created_at="2026-09-24T10:00:00+05:30",
    )
    validating = controller.transition(candidate, CandidateLifecycle.VALIDATING, at="2026-09-24T10:01:00+05:30")
    paper = controller.transition(validating, CandidateLifecycle.PAPER, at="2026-09-24T10:02:00+05:30")

    assert store.count("candidate") == 3
    assert [row["lifecycle"] for row in store.records("candidate")] == [
        "CANDIDATE",
        "VALIDATING",
        "PAPER",
    ]


def test_wrong_types_are_rejected() -> None:
    controller = CandidateLifecycleController()
    with pytest.raises(TypeError, match="candidate must"):
        controller.transition(object(), CandidateLifecycle.VALIDATING, at="now")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="target must"):
        controller.transition(_candidate(), "VALIDATING", at="now")  # type: ignore[arg-type]
