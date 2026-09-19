"""
Tests for Phase 9 training orchestration.

These tests verify that:
    - temporal splitting happens before learned preprocessing
    - preprocessing is fitted only on training data
    - the model is fitted only on training data
    - validation is transformed but not fitted
    - test data is not evaluated by the trainer
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import ml.training.trainer as trainer_module
from ml.datasets import TrainingDataset
from ml.preprocessing import (
    BOOLEAN_FEATURES,
    NUMERIC_FEATURES,
)
from ml.training import (
    TrainingConfig,
    TrainingResult,
    train_baseline,
    train_random_forest,
)


def make_dataset(rows: int = 300) -> TrainingDataset:
    """Create deterministic supervised training data."""

    rng = np.random.default_rng(42)

    timestamps = pd.date_range(
        "2025-01-01 09:15",
        periods=rows,
        freq="5min",
        tz="Asia/Kolkata",
    )

    data = {}

    for column in NUMERIC_FEATURES:
        data[column] = rng.normal(
            size=rows
        )

    for column in BOOLEAN_FEATURES:
        data[column] = pd.Series(
            rng.choice(
                [True, False],
                size=rows,
            ),
            dtype="boolean",
        )

    data["timestamp"] = timestamps
    data["symbol"] = ["TEST"] * rows

    labels = (
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    )

    data["label"] = [
        labels[index % len(labels)]
        for index in range(rows)
    ]

    return TrainingDataset(
        data=pd.DataFrame(data),
        feature_columns=(
            tuple(NUMERIC_FEATURES)
            + tuple(sorted(BOOLEAN_FEATURES))
        ),
    )


def test_train_baseline_returns_training_result():
    """Training produces the documented result object."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    assert isinstance(
        result,
        TrainingResult,
    )


def test_training_result_has_valid_partition_sizes():
    """All three chronological partitions contain observations."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    assert result.train_rows > 0
    assert result.validation_rows > 0
    assert result.test_rows > 0

    assert (
        result.train_rows
        + result.validation_rows
        + result.test_rows
        < len(dataset.data)
    )


def test_preprocessor_and_model_are_fitted():
    """Both learned components are fitted successfully."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    assert result.preprocessor.is_fitted
    assert result.model.is_fitted
    assert result.calibrator.is_fitted


def test_validation_probabilities_have_canonical_schema():
    """Validation output uses the canonical three-class schema."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    assert list(
        result.validation_probabilities.columns
    ) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]

    assert (
        result.validation_probabilities.shape[0]
        == result.validation_rows
    )

    assert (
        result.validation_probabilities.shape[1]
        == 3
    )


def test_validation_probability_rows_sum_to_one():
    """Each validation probability vector is a valid distribution."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    row_sums = (
        result.validation_probabilities
        .sum(axis=1)
    )

    np.testing.assert_allclose(
        row_sums.to_numpy(),
        np.ones(result.validation_rows),
        rtol=0,
        atol=1e-10,
    )


def test_validation_predictions_are_model_classes():
    """Predictions are restricted to the three model classes."""

    dataset = make_dataset()

    result = train_baseline(dataset)

    predictions = result.validation_predictions

    assert len(predictions) == result.validation_rows

    assert set(predictions).issubset(
        {
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        }
    )


def test_training_only_fit_boundary(monkeypatch):
    """
    Verify the trainer fits learned components only on TRAIN.

    Spy components record the rows supplied to fit_transform/model.fit
    and transform. The expected validation transform count proves that
    TEST is never passed through the trainer.
    """

    dataset = make_dataset()

    calls = {
        "preprocessor_fit_rows": None,
        "preprocessor_transform_rows": [],
        "model_fit_rows": None,
        "calibrator_fit_rows": None,
        "calibrator_transform_rows": None,
    }

    class SpyPreprocessor:
        """Minimal preprocessing spy."""

        def __init__(self, config):
            self.config = config
            self.is_fitted = False

        def fit_transform(self, X):
            calls["preprocessor_fit_rows"] = len(X)
            self.is_fitted = True

            return np.zeros(
                (len(X), len(X.columns)),
                dtype=float,
            )

        def transform(self, X):
            calls[
                "preprocessor_transform_rows"
            ].append(len(X))

            return np.zeros(
                (len(X), len(X.columns)),
                dtype=float,
            )

    class SpyCalibrator:
        """Minimal probability-calibration spy."""

        def __init__(self):
            self.is_fitted = False

        def fit(self, probabilities, y_true):
            calls["calibrator_fit_rows"] = len(probabilities)
            self.is_fitted = True
            return self

        def transform(self, probabilities):
            calls["calibrator_transform_rows"] = len(probabilities)
            return probabilities

    class SpyModel:
        """Minimal model-training spy."""

        def __init__(self, config):
            self.config = config
            self.is_fitted = False

        def fit(self, X, y):
            calls["model_fit_rows"] = len(X)
            self.is_fitted = True

        def predict_proba(self, X):
            probabilities = np.tile(
                [1 / 3, 1 / 3, 1 / 3],
                (len(X), 1),
            )

            return pd.DataFrame(
                probabilities,
                columns=[
                    "LONG_SUCCESS",
                    "SHORT_SUCCESS",
                    "NO_EDGE",
                ],
            )

    monkeypatch.setattr(
        trainer_module,
        "FeaturePreprocessor",
        SpyPreprocessor,
    )

    monkeypatch.setattr(
        trainer_module,
        "LogisticOutcomeModel",
        SpyModel,
    )

    monkeypatch.setattr(
        trainer_module,
        "IsotonicProbabilityCalibrator",
        SpyCalibrator,
    )

    result = train_baseline(dataset)

    assert (
        calls["preprocessor_fit_rows"]
        == result.train_rows
    )

    assert (
        calls["model_fit_rows"]
        == result.train_rows
    )

    assert calls["preprocessor_fit_rows"] == result.train_rows
    assert calls["model_fit_rows"] == result.train_rows

    assert calls["preprocessor_transform_rows"] == [
        result.calibration_rows,
        result.validation_rows,
    ]

    assert calls["calibrator_fit_rows"] == result.calibration_rows
    assert calls["calibrator_transform_rows"] == result.validation_rows


def test_default_training_config_matches_phase9_baseline():
    """Default training configuration remains reproducible."""

    config = TrainingConfig()

    assert config.split.train_ratio == 0.70
    assert config.split.validation_ratio == 0.15
    assert config.split.test_ratio == 0.15
    assert config.split.purge_minutes == 60

    assert config.preprocessing.scale_numeric is True

    assert config.model.C == 1.0
    assert config.model.max_iter == 1000
    assert config.model.random_state == 42


def test_train_random_forest_returns_calibrated_training_result():
    """Random Forest uses the same leakage-safe training contract."""
    dataset = make_dataset()

    result = train_random_forest(dataset)

    assert isinstance(result, TrainingResult)
    assert result.preprocessor.is_fitted
    assert result.model.is_fitted
    assert result.calibrator.is_fitted
    assert list(result.validation_probabilities.columns) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]
    assert result.validation_rows == len(result.validation_probabilities)
    np.testing.assert_allclose(
        result.validation_probabilities.sum(axis=1).to_numpy(),
        np.ones(result.validation_rows),
        rtol=0,
        atol=1e-10,
    )
