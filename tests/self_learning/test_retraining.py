"""Tests for controlled real-data candidate retraining."""

from __future__ import annotations

from typing import Any

import hashlib
import pandas as pd
import pytest

from market.features.builder import FEATURE_COLUMNS
from ml.datasets.models import TrainingDataset
from ml.preprocessing.models import BOOLEAN_FEATURES, PreprocessingConfig
from ml.training.models import TrainingConfig
from ml.datasets.splitting import TemporalSplitConfig
from self_learning.contracts import DatasetVersion, ExperimentSpec
from self_learning.dataset import build_dataset_version, dataframe_fingerprint
from self_learning.retraining import _default_artifact_serializer, retrain_candidate


def _dataset() -> TrainingDataset:
    timestamps = pd.date_range("2026-01-01 09:15", periods=240, freq="5min")
    rows: list[dict[str, object]] = []
    labels = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")
    for index, timestamp in enumerate(timestamps):
        for symbol_offset, symbol in enumerate(("AAA", "BBB")):
            row: dict[str, object] = {
                "timestamp": timestamp,
                "symbol": symbol,
                "label": labels[(index + symbol_offset) % len(labels)],
            }
            for feature_offset, feature in enumerate(FEATURE_COLUMNS):
                if feature in BOOLEAN_FEATURES:
                    row[feature] = bool((index + symbol_offset + feature_offset) % 2)
                else:
                    row[feature] = float(index + symbol_offset + feature_offset * 0.01)
            rows.append(row)
    frame = pd.DataFrame(rows)
    return TrainingDataset(data=frame, feature_columns=FEATURE_COLUMNS)


def _provenance(dataset: TrainingDataset) -> DatasetVersion:
    return build_dataset_version(
        dataset,
        dataset_version="phase9-test-v1",
        source="phase9-test.parquet",
        creation_timestamp="2026-09-24T21:30:00+05:30",
        feature_schema_version="phase9-features-v1",
        label_definition_version="phase9-labels-v1",
    )


def _config() -> TrainingConfig:
    return TrainingConfig(
        split=TemporalSplitConfig(
            train_ratio=0.70,
            validation_ratio=0.15,
            test_ratio=0.15,
            purge_minutes=60,
        ),
        preprocessing=PreprocessingConfig(
            numeric_strategy="median",
            boolean_strategy="most_frequent",
            scale_numeric=True,
        ),
        calibration_ratio=0.15,
    )


def _experiment(dataset_version: str = "phase9-test-v1") -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="EXP-RETRAIN-1",
        research_question="Does controlled retraining preserve the Phase-9 protocol?",
        hypothesis="The existing trainer produces a reproducible candidate.",
        null_hypothesis="The candidate protocol does not produce a valid result.",
        failure_criterion="Reject if training protocol or provenance binding fails.",
        dataset_version=dataset_version,
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
        dataset, dataset_version=_provenance(dataset),
        experiment=_experiment(), trainer="logistic_regression", config=_config()
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
        dataset, dataset_version=_provenance(dataset),
        experiment=_experiment(), trainer="random_forest", config=_config()
    )
    assert result.model_family == "random_forest"
    assert result.status == "CANDIDATE"
    assert len(result.artifact_fingerprint) == 64


def test_dataset_provenance_mismatch_is_rejected() -> None:
    dataset = _dataset()
    other = _dataset()
    other.data.loc[0, "feature_a"] = 999.0 if "feature_a" in other.data else other.data.loc[0, FEATURE_COLUMNS[0]] + 999.0
    with pytest.raises(ValueError, match="does not match DatasetVersion source fingerprint"):
        retrain_candidate(other, dataset_version=_provenance(dataset), experiment=_experiment(), config=_config())


def test_experiment_dataset_version_mismatch_is_rejected() -> None:
    dataset = _dataset()
    with pytest.raises(ValueError, match="experiment and dataset versions"):
        retrain_candidate(
            dataset,
            dataset_version=_provenance(dataset),
            experiment=_experiment("different-version"),
            config=_config(),
        )


def test_unsupported_trainer_is_rejected() -> None:
    dataset = _dataset()
    with pytest.raises(ValueError, match="unsupported candidate trainer"):
        retrain_candidate(
            dataset, dataset_version=_provenance(dataset),
            experiment=_experiment(), trainer="unknown", config=_config()
        )


def test_wrong_contract_types_are_rejected() -> None:
    dataset = _dataset()
    version = _provenance(dataset)
    experiment = _experiment()
    with pytest.raises(TypeError, match="TrainingDataset"):
        retrain_candidate(object(), dataset_version=version, experiment=experiment, config=_config())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="DatasetVersion"):
        retrain_candidate(dataset, dataset_version=object(), experiment=experiment, config=_config())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ExperimentSpec"):
        retrain_candidate(dataset, dataset_version=version, experiment=object(), config=_config())  # type: ignore[arg-type]


def test_custom_artifact_serializer_is_hashed_as_bytes() -> None:
    dataset = _dataset()
    result = retrain_candidate(
        dataset, dataset_version=_provenance(dataset), experiment=_experiment(),
        artifact_serializer=lambda model: b"candidate-artifact-v1", config=_config()
    )
    assert result.artifact_fingerprint == hashlib.sha256(b"candidate-artifact-v1").hexdigest()


def test_artifact_serializer_must_return_bytes() -> None:
    dataset = _dataset()
    with pytest.raises(TypeError, match="must return bytes"):
        retrain_candidate(
            dataset, dataset_version=_provenance(dataset), experiment=_experiment(),
            artifact_serializer=lambda model: "not-bytes", config=_config()  # type: ignore[return-value]
        )


def test_default_artifact_identity_includes_fitted_state() -> None:
    dataset = _dataset()
    first = retrain_candidate(dataset, dataset_version=_provenance(dataset), experiment=_experiment(), config=_config())
    changed = _dataset()
    changed.data.loc[0, FEATURE_COLUMNS[0]] = changed.data.loc[0, FEATURE_COLUMNS[0]] + 50.0
    changed_version = _provenance(changed)
    changed_experiment = _experiment()
    object.__setattr__(changed_experiment, "dataset_version", changed_version.dataset_version)
    second = retrain_candidate(changed, dataset_version=changed_version, experiment=changed_experiment, config=_config())
    assert first.artifact_fingerprint != second.artifact_fingerprint


def test_default_artifact_serializer_is_stable_for_same_fitted_model() -> None:
    dataset = _dataset()
    first = retrain_candidate(dataset, dataset_version=_provenance(dataset), experiment=_experiment(), config=_config())
    second = retrain_candidate(dataset, dataset_version=_provenance(dataset), experiment=_experiment(), config=_config())
    assert first.artifact_fingerprint == second.artifact_fingerprint


def test_source_fingerprint_matches_actual_dataset() -> None:
    dataset = _dataset()
    version = _provenance(dataset)
    assert dataframe_fingerprint(dataset.data) in version.source_fingerprints
    retrained = retrain_candidate(dataset, dataset_version=version, experiment=_experiment(), config=_config())
    assert len(_default_artifact_serializer(retrained.result)) > 0
