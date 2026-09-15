"""
Tests for the Phase 9 Logistic Regression outcome model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.models import (
    MODEL_CLASSES,
    LogisticOutcomeModel,
    LogisticRegressionConfig,
)


def make_training_data(
    rows_per_class: int = 30,
) -> tuple[np.ndarray, np.ndarray]:
    """Create deterministic three-class model data."""

    rng = np.random.default_rng(42)

    X = rng.normal(
        size=(rows_per_class * 3, 40)
    )

    y = np.array(
        ["LONG_SUCCESS"] * rows_per_class
        + ["SHORT_SUCCESS"] * rows_per_class
        + ["NO_EDGE"] * rows_per_class
    )

    return X, y


def test_model_configuration_defaults():
    """Model v1 must have stable default configuration."""

    config = LogisticRegressionConfig()

    assert config.C == 1.0
    assert config.max_iter == 1000
    assert config.random_state == 42


def test_invalid_model_configuration_is_rejected():
    """Invalid model hyperparameters must fail explicitly."""

    with pytest.raises(
        ValueError,
        match="C must be greater",
    ):
        LogisticRegressionConfig(C=0)

    with pytest.raises(
        ValueError,
        match="max_iter must be greater",
    ):
        LogisticRegressionConfig(max_iter=0)


def test_model_starts_unfitted():
    """A newly constructed model must not claim to be fitted."""

    model = LogisticOutcomeModel()

    assert not model.is_fitted


def test_prediction_before_fit_is_rejected():
    """Prediction must require a fitted model."""

    X, _ = make_training_data()

    model = LogisticOutcomeModel()

    with pytest.raises(
        RuntimeError,
        match="must be fitted",
    ):
        model.predict_proba(X[:5])


def test_model_fits_three_classes():
    """The model must fit the three frozen prediction classes."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    returned = model.fit(X, y)

    assert returned is model
    assert model.is_fitted
    assert model.feature_count == 40


def test_model_reports_canonical_classes():
    """Public class ordering must be deterministic."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    model.fit(X, y)

    assert model.classes == (
        "LONG_SUCCESS",
        "NO_EDGE",
        "SHORT_SUCCESS",
    )

    assert set(model.classes) == set(
        MODEL_CLASSES
    )


def test_predict_proba_has_three_columns():
    """Prediction must return exactly three outcome probabilities."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    model.fit(X, y)

    probabilities = model.predict_proba(
        X[:10]
    )

    assert list(probabilities.columns) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]

    assert probabilities.shape == (10, 3)


def test_probabilities_are_valid():
    """Every probability must be finite and lie in [0, 1]."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    model.fit(X, y)

    probabilities = model.predict_proba(
        X[:20]
    )

    values = probabilities.to_numpy(
        dtype=float
    )

    assert np.isfinite(values).all()
    assert (values >= 0.0).all()
    assert (values <= 1.0).all()


def test_probabilities_sum_to_one():
    """Multiclass probabilities must form a valid distribution."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    model.fit(X, y)

    probabilities = model.predict_proba(
        X[:20]
    )

    np.testing.assert_allclose(
        probabilities.sum(axis=1).to_numpy(),
        1.0,
        atol=1e-8,
    )


def test_invalid_training_labels_are_rejected():
    """Only the three frozen prediction labels are allowed."""

    X, y = make_training_data()

    y[0] = "INVALID"

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="invalid prediction labels",
    ):
        model.fit(X, y)


def test_missing_phase9_class_training_is_rejected():
    """Training must contain all three Phase 9 outcome classes."""

    X, _ = make_training_data()

    y = np.array(
        ["LONG_SUCCESS"] * 30
        + ["SHORT_SUCCESS"] * 30
        + ["LONG_SUCCESS"] * 30
    )

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="all three Phase 9 prediction classes",
    ):
        model.fit(X, y)


def test_x_y_length_mismatch_is_rejected():
    """Feature rows and labels must have identical length."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="same number of rows",
    ):
        model.fit(X, y[:-1])


def test_wrong_x_dimensions_are_rejected():
    """The model requires a two-dimensional feature matrix."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="two-dimensional",
    ):
        model.fit(
            X[0],
            y[0:1],
        )


def test_empty_x_is_rejected():
    """An empty feature matrix is invalid."""

    _, y = make_training_data()

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="at least one row",
    ):
        model.fit(
            np.empty((0, 40)),
            y[:0],
        )


def test_non_finite_x_is_rejected():
    """Preprocessing must guarantee finite values before the model."""

    X, y = make_training_data()

    X[0, 0] = np.nan

    model = LogisticOutcomeModel()

    with pytest.raises(
        ValueError,
        match="finite values",
    ):
        model.fit(X, y)


def test_non_numpy_x_is_rejected():
    """The model accepts only the preprocessed ndarray contract."""

    X, y = make_training_data()

    model = LogisticOutcomeModel()

    with pytest.raises(
        TypeError,
        match="numpy ndarray",
    ):
        model.fit(
            pd.DataFrame(X),
            y,
        )


def test_model_is_deterministic():
    """Identical data/configuration must produce identical probabilities."""

    X, y = make_training_data()

    first = LogisticOutcomeModel()
    second = LogisticOutcomeModel()

    first.fit(X, y)
    second.fit(X, y)

    first_probabilities = first.predict_proba(
        X[:20]
    )

    second_probabilities = second.predict_proba(
        X[:20]
    )

    pd.testing.assert_frame_equal(
        first_probabilities,
        second_probabilities,
    )
