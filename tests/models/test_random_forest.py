"""Tests for the Phase 9 Random Forest benchmark model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.models.random_forest import (
    MODEL_CLASSES,
    RandomForestConfig,
    RandomForestOutcomeModel,
)


def make_training_data(
    rows_per_class: int = 12,
) -> tuple[np.ndarray, pd.Series]:
    """Create deterministic, separable three-class training data."""
    rows = []
    labels = []
    centers = {
        "LONG_SUCCESS": 1.0,
        "SHORT_SUCCESS": -1.0,
        "NO_EDGE": 0.0,
    }

    for label, center in centers.items():
        for offset in range(rows_per_class):
            rows.append([center + offset * 0.001, center * 0.5])
            labels.append(label)

    return np.asarray(rows, dtype=float), pd.Series(labels)


def test_random_forest_fits_and_returns_canonical_probabilities() -> None:
    """The benchmark must expose valid probabilities in fixed class order."""
    X, y = make_training_data()
    model = RandomForestOutcomeModel(
        RandomForestConfig(
            n_estimators=40,
            min_samples_leaf=1,
        )
    )

    model.fit(X, y)
    probabilities = model.predict_proba(X[:5])

    assert model.is_fitted is True
    assert model.feature_count == 2
    assert tuple(probabilities.columns) == MODEL_CLASSES
    assert np.isfinite(probabilities.to_numpy()).all()
    assert np.allclose(probabilities.sum(axis=1), 1.0)


def test_random_forest_rejects_missing_prediction_class() -> None:
    """Training must not silently create a two-class Phase 9 model."""
    X, y = make_training_data()
    y = y.replace("NO_EDGE", "LONG_SUCCESS")
    model = RandomForestOutcomeModel()

    with pytest.raises(
        ValueError,
        match="all three Phase 9 prediction classes",
    ):
        model.fit(X, y)
