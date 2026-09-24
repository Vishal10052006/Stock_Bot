"""Tests for controlled real-data candidate retraining."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.datasets.models import TrainingDataset
from self_learning.contracts import DatasetVersion, ExperimentSpec
from self_learning.dataset import build_dataset_version, dataframe_fingerprint
from self_learning.retraining import (
    _default_artifact_serializer,
    retrain_candidate,
)


def _dataset() -> TrainingDataset:
    # The production splitter uses a 60-minute purge on both sides of
    # each boundary. Keep the fixture large enough that the validation
    # interval remains non-empty under that real protocol.
    timestamps = pd.date_range(
        "2026-01-01 09:15",
        periods=240,
        freq="5min",
    )
    rows: list[dict[str, object]] = []
    labels = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")

    for index, timestamp in enumerate(timestamps):
        for symbol_offset, symbol in enumerate(("AAA", "BBB")):
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "feature_a": float(index + symbol_offset),
                    "feature_b": float((index % 9) + symbol_offset * 0.5),
                    "label": labels[(index + symbol_offset) % len(labels)],
                }
            )

    frame = pd.DataFrame(rows)
    return TrainingDataset(
        data=frame,
        feature_columns=("feature_a", "feature_b"),
    )


def _provenance(dataset: TrainingDataset) -> DatasetVersion:
    return build_dataset_version(
        dataset,
        dataset_version="phase9-test-v1",
        source="phase9-test.parquet",
        creation_timestamp="2026-09-24T21:30:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )


def _experiment() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="EXP-RETRAIN-1",
        research_question="Does controlled retraining preserve the Phase-9 protocol?",
        hypothesis="The existing trainer produces a reproducible candidate.",
        null_hypothesis="The candidate protocol does not produce a valid result.",
        failure_criterion="Reject if training protocol or provenance binding fails.",
        dataset_version="phase9-test-v1",
        code_version="test-code-v1",
        feature_version="phase9-features-v1",
        label_version="phase9-labels-v1",
        model_version="model-baseline-v1",
        strategy_version="strategy-v1",
        risk_version="risk-v1",
        execution_version="execution-v1",
        period_start="2026-01-01T09:15:00",
        period_end="2026-01-02T05:10:00",
        symbols=("AAA", "BBB"),
        method="chronological-phase9-retraining",
        changed_component="model",
        changed_parameter="trainer",
        baseline_fingerprints={"baseline": "a" * 64},
    )


def test_logistic_retraining_returns_candidate() -> None:
    dataset = _dataset()
    result = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
        trainer="logistic_regression",
    )

    assert result.model_family == "logistic_regression"
    assert result.dataset_version == "phase9-test-v1"
    assert result.status == "CANDIDATE"
    assert len(result.experiment_fingerprint) == 64
    assert len(result.artifact_fingerprint) == 64
    assert result.result.train_rows > 0
    assert result.result.calibration_rows > 0
    assert result.result.validation_rows > 0
    assert result.result.test_rows > 0


def test_random_forest_retraining_is_explicit_candidate() -> None:
    dataset = _dataset()
    result = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
        trainer="random_forest",
    )

    assert result.model_family == "random_forest"
    assert result.status == "CANDIDATE"
    assert len(result.artifact_fingerprint) == 64


def test_dataset_provenance_mismatch_is_rejected() -> None:
    dataset = _dataset()
    other = _dataset()
    other.data.loc[0, "feature_a"] = 999.0

    with pytest.raises(
        ValueError,
        match="does not match DatasetVersion source fingerprint",
    ):
        retrain_candidate(
            other,
            dataset_version=_provenance(dataset),
            experiment=_experiment(),
        )


def test_experiment_dataset_version_mismatch_is_rejected() -> None:
    dataset = _dataset()
    version = _provenance(dataset)
    experiment = _experiment()
    object.__setattr__(experiment, "dataset_version", "different-version")

    with pytest.raises(ValueError, match="experiment and dataset versions"):
        retrain_candidate(
            dataset,
            dataset_version=version,
            experiment=experiment,
        )


def test_unsupported_trainer_is_rejected() -> None:
    dataset = _dataset()

    with pytest.raises(ValueError, match="unsupported candidate trainer"):
        retrain_candidate(
            dataset,
            dataset_version=_provenance(dataset),
            experiment=_experiment(),
            trainer="unknown",
        )


def test_wrong_contract_types_are_rejected() -> None:
    dataset = _dataset()
    version = _provenance(dataset)
    experiment = _experiment()

    with pytest.raises(TypeError, match="TrainingDataset"):
        retrain_candidate(
            object(),  # type: ignore[arg-type]
            dataset_version=version,
            experiment=experiment,
        )

    with pytest.raises(TypeError, match="DatasetVersion"):
        retrain_candidate(
            dataset,
            dataset_version=object(),  # type: ignore[arg-type]
            experiment=experiment,
        )

    with pytest.raises(TypeError, match="ExperimentSpec"):
        retrain_candidate(
            dataset,
            dataset_version=version,
            experiment=object(),  # type: ignore[arg-type]
        )


def test_custom_artifact_serializer_is_hashed_as_bytes() -> None:
    dataset = _dataset()

    result = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
        artifact_serializer=lambda model: b"candidate-artifact-v1",
    )

    import hashlib

    assert result.artifact_fingerprint == hashlib.sha256(
        b"candidate-artifact-v1"
    ).hexdigest()


def test_artifact_serializer_must_return_bytes() -> None:
    dataset = _dataset()

    with pytest.raises(TypeError, match="must return bytes"):
        retrain_candidate(
            dataset,
            dataset_version=_provenance(dataset),
            experiment=_experiment(),
            artifact_serializer=lambda model: "not-bytes",  # type: ignore[return-value]
        )


def test_default_artifact_identity_includes_fitted_state() -> None:
    dataset = _dataset()
    first = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
    )

    changed = _dataset()
    changed.data.loc[0, "feature_a"] = 50.0
    changed_version = build_dataset_version(
        changed,
        dataset_version="phase9-test-v2",
        source="phase9-test-v2.parquet",
        creation_timestamp="2026-09-24T21:30:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )
    changed_experiment = _experiment()
    object.__setattr__(changed_experiment, "dataset_version", "phase9-test-v2")

    second = retrain_candidate(
        changed,
        dataset_version=changed_version,
        experiment=changed_experiment,
    )

    assert first.artifact_fingerprint != second.artifact_fingerprint


def test_default_artifact_serializer_is_stable_for_same_fitted_model() -> None:
    dataset = _dataset()
    first = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
    )
    second = retrain_candidate(
        dataset,
        dataset_version=_provenance(dataset),
        experiment=_experiment(),
    )

    assert first.artifact_fingerprint == second.artifact_fingerprint


def test_source_fingerprint_matches_actual_dataset() -> None:
    dataset = _dataset()
    version = _provenance(dataset)

    assert dataframe_fingerprint(dataset.data) in version.source_fingerprints
    retrained = retrain_candidate(
        dataset,
        dataset_version=version,
        experiment=_experiment(),
    )
    assert len(_default_artifact_serializer(retrained.result)) > 0
