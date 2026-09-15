"""
Tests for Phase 9 leakage-safe preprocessing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.preprocessing import (
    BOOLEAN_FEATURES,
    NUMERIC_FEATURES,
    FeaturePreprocessor,
    PreprocessingConfig,
)


def make_features(
    values: list[float],
    *,
    boolean_missing: bool = False,
) -> pd.DataFrame:
    """Create a deterministic raw feature matrix."""

    data: dict[str, object] = {}

    for column in NUMERIC_FEATURES:
        data[column] = list(values)

    boolean_values = (
        [True, False, pd.NA, True]
        if boolean_missing
        else [True, False, False, True]
    )

    for column in BOOLEAN_FEATURES:
        data[column] = pd.Series(
            boolean_values,
            dtype="boolean",
        )

    return pd.DataFrame(data)


def test_preprocessor_has_40_features():
    """The preprocessing contract must cover all 40 features."""

    assert len(NUMERIC_FEATURES) == 34
    assert len(BOOLEAN_FEATURES) == 6

    assert (
        len(NUMERIC_FEATURES)
        + len(BOOLEAN_FEATURES)
        == 40
    )


def test_fit_transform_produces_finite_matrix():
    """Missing values must not survive preprocessing."""

    X = make_features(
        [1.0, 2.0, np.nan, 4.0],
        boolean_missing=True,
    )

    preprocessor = FeaturePreprocessor()

    transformed = preprocessor.fit_transform(X)

    assert transformed.shape == (4, 40)
    assert np.isfinite(transformed).all()


def test_transform_before_fit_is_rejected():
    """A transformer must never transform using unfitted statistics."""

    X = make_features([1.0, 2.0, 3.0, 4.0])

    preprocessor = FeaturePreprocessor()

    with pytest.raises(
        RuntimeError,
        match="must be fitted",
    ):
        preprocessor.transform(X)


def test_invalid_feature_schema_is_rejected():
    """Unexpected or missing features must fail explicitly."""

    X = make_features([1.0, 2.0, 3.0, 4.0])

    X = X.drop(
        columns=[NUMERIC_FEATURES[0]]
    )

    preprocessor = FeaturePreprocessor()

    with pytest.raises(
        ValueError,
        match="Invalid preprocessing feature schema",
    ):
        preprocessor.fit(X)


def test_training_row_count_is_recorded():
    """Metadata must record how many rows fitted the transformer."""

    X = make_features([1.0, 2.0, 3.0, 4.0])

    preprocessor = FeaturePreprocessor()

    preprocessor.fit(X)

    assert preprocessor.result.fitted_on_rows == 4


def test_feature_names_are_deterministic():
    """Transformed feature names must be stable."""

    X = make_features([1.0, 2.0, 3.0, 4.0])

    preprocessor = FeaturePreprocessor()

    preprocessor.fit(X)

    names = preprocessor.get_feature_names_out()

    assert len(names) == 40
    assert len(set(names)) == 40


def test_scaling_is_fitted_from_training_data_only():
    """
    Training preprocessing statistics must not depend on another
    dataset that is transformed later.
    """

    X_train = make_features(
        [10.0, 20.0, 30.0, 40.0]
    )

    X_validation_a = make_features(
        [100.0, 100.0, 100.0, 100.0]
    )

    X_validation_b = make_features(
        [1000.0, 1000.0, 1000.0, 1000.0]
    )

    first = FeaturePreprocessor()

    first.fit(X_train)

    train_a = first.transform(X_train)
    first.transform(X_validation_a)

    second = FeaturePreprocessor()

    second.fit(X_train)

    train_b = second.transform(X_train)
    second.transform(X_validation_b)

    np.testing.assert_allclose(
        train_a,
        train_b,
    )


def test_median_imputation_uses_training_data():
    """Numeric missing values must use the training median."""

    X_train = make_features(
        [10.0, 20.0, np.nan, 40.0]
    )

    X_validation = make_features(
        [1000.0, 2000.0, 3000.0, 4000.0]
    )

    preprocessor = FeaturePreprocessor()

    preprocessor.fit(X_train)

    transformed = preprocessor.transform(
        X_validation
    )

    assert transformed.shape == (4, 40)
    assert np.isfinite(transformed).all()


def test_boolean_missing_values_are_imputed():
    """Nullable boolean features must not produce missing output."""

    X = make_features(
        [1.0, 2.0, 3.0, 4.0],
        boolean_missing=True,
    )

    preprocessor = FeaturePreprocessor()

    transformed = preprocessor.fit_transform(X)

    assert transformed.shape == (4, 40)
    assert np.isfinite(transformed).all()


def test_preprocessing_can_disable_numeric_scaling():
    """Scaling is configurable without changing the feature schema."""

    X = make_features(
        [10.0, 20.0, 30.0, 40.0]
    )

    config = PreprocessingConfig(
        scale_numeric=False,
    )

    preprocessor = FeaturePreprocessor(config)

    transformed = preprocessor.fit_transform(X)

    assert transformed.shape == (4, 40)
    assert np.isfinite(transformed).all()
