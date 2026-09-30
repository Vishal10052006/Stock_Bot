"""Tests for Self-Learning contract integrity and safety boundaries."""

import pandas as pd
import pytest

from self_learning.contracts import (
    DatasetVersion,
    ExperimentLifecycle,
    ExperimentSpec,
    LearningEvidence,
    LearningTrigger,
    ModelCandidate,
    PromotionState,
)
from self_learning.dataset import build_dataset_version, dataframe_fingerprint
from ml.datasets.models import TrainingDataset


def _dataset() -> TrainingDataset:
    return TrainingDataset(
        data=pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2026-01-01 09:15",
                    periods=6,
                    freq="5min",
                    tz="Asia/Kolkata",
                ),
                "symbol": ["ITC"] * 6,
                "feature_a": [1, 2, 3, 4, 5, 6],
                "label": ["LONG_SUCCESS", "NO_EDGE", "SHORT_SUCCESS",
                          "NO_EDGE", "LONG_SUCCESS", "SHORT_SUCCESS"],
            }
        ),
        feature_columns=("feature_a",),
    )


def test_dataset_fingerprint_is_deterministic() -> None:
    assert dataframe_fingerprint(_dataset().data) == dataframe_fingerprint(_dataset().data)


def test_dataset_version_preserves_provenance() -> None:
    version = build_dataset_version(
        _dataset(),
        dataset_version="dataset-v1",
        source="phase9-training",
        creation_timestamp="2026-09-24T10:00:00+05:30",
        feature_schema_version="features-v1",
        label_definition_version="labels-v1",
    )
    assert version.row_count == 6
    assert version.symbols == ("ITC",)
    assert version.label_distribution["LONG_SUCCESS"] == 2
    assert len(version.source_fingerprints) == 1


def test_learning_evidence_rejects_wrong_trade_count() -> None:
    with pytest.raises(ValueError, match="source_trade_ids count"):
        LearningEvidence(
            evidence_id="E1",
            pattern="LOSS",
            error_class="OUTCOME_LOSS",
            source_trade_ids=("T1",),
            evidence_count=2,
            population_count=3,
            occurrence_rate=2 / 3,
            confidence=0.4,
            average_reward=-0.5,
            rationale="Repeated evidence.",
        )


def test_experiment_is_explicitly_one_primary_change() -> None:
    spec = ExperimentSpec(
        experiment_id="EXP-1",
        research_question="Does X improve robustness?",
        hypothesis="X improves OOS quality.",
        null_hypothesis="X does not improve OOS quality.",
        failure_criterion="Reject if OOS robustness degrades.",
        dataset_version="dataset-v1",
        code_version="code-v1",
        feature_version="features-v1",
        label_version="labels-v1",
        model_version="model-v1",
        strategy_version="strategy-v1",
        risk_version="risk-v1",
        execution_version="execution-v1",
        period_start="2025-01-01",
        period_end="2026-01-01",
        symbols=("ITC",),
        method="temporal-oos-walk-forward",
        changed_component="strategy",
        changed_parameter="baseline.minimum_rvol",
        baseline_fingerprints={"strategy": "a" * 64},
        trigger_evidence_fingerprint="b" * 64,
    )
    assert spec.lifecycle is ExperimentLifecycle.PROPOSED
    assert len(spec.fingerprint) == 64


def test_promotion_state_requires_explicit_approval() -> None:
    from self_learning.contracts import PromotionDecision

    with pytest.raises(ValueError, match="approval_reference"):
        PromotionDecision(
            candidate_id="C1",
            candidate_fingerprint="a" * 64,
            champion_version="v1",
            challenger_version="v2",
            state=PromotionState.PROMOTED,
            reasons=(),
            validation_fingerprints=("b" * 64,),
        )


def test_model_candidate_has_reproducible_identity() -> None:
    candidate = ModelCandidate(
        candidate_id="C1",
        candidate_version="model-v2",
        candidate_type="logistic_regression",
        lifecycle=__import__("self_learning.contracts", fromlist=["CandidateLifecycle"]).CandidateLifecycle.CANDIDATE,
        dataset_version="dataset-v1",
        feature_version="features-v1",
        label_version="labels-v1",
        source_experiment_id="EXP-1",
        source_experiment_fingerprint="a" * 64,
        artifact_fingerprint="b" * 64,
        evaluation_fingerprint="c" * 64,
        lineage_id="d" * 64,
        metrics={"balanced_accuracy": 0.5},
        parent_model_version="model-v1",
        strategy_version="strategy-v1",
        created_at="2026-09-24T10:00:00+05:30",
    )
    assert len(candidate.fingerprint) == 64
    assert candidate.fingerprint == candidate.fingerprint
