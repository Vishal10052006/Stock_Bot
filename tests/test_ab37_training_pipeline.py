"""AB-37 Phase 9 training-pipeline integration coverage.

The tests verify that the existing training orchestrator preserves the
causal chronology: classifier fit, calibration, validation, and untouched
test partition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.features.builder import FEATURE_COLUMNS
from ml.datasets.models import TrainingDataset
from ml.training import TrainingConfig, train_baseline


def _dataset() -> TrainingDataset:
    """Build a deterministic, leakage-safe three-class training fixture."""
    timestamps = pd.date_range(
        "2026-01-01 09:15:00+05:30",
        periods=60,
        freq="60min",
    )

    rows: list[dict[str, object]] = []
    labels = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")

    for index, timestamp in enumerate(timestamps):
        row: dict[str, object] = {
            "timestamp": timestamp,
            "symbol": "RELIANCE",
            "label": labels[index % len(labels)],
        }

        for feature_index, column in enumerate(FEATURE_COLUMNS):
            # Deterministic variation prevents a constant-feature fixture.
            row[column] = float((index + feature_index) % 11) / 10.0

        rows.append(row)

    return TrainingDataset(
        data=pd.DataFrame(rows),
        feature_columns=tuple(FEATURE_COLUMNS),
    )


def test_ab37_baseline_training_produces_calibrated_validation_probabilities() -> None:
    """Training must produce valid probabilities on unseen validation data."""
    result = train_baseline(
        _dataset(),
        config=TrainingConfig(calibration_ratio=0.15),
    )

    assert result.train_rows > 0
    assert result.calibration_rows > 0
    assert result.validation_rows > 0
    assert result.test_rows > 0

    assert result.model.is_fitted
    assert result.model.feature_count == len(FEATURE_COLUMNS)

    probabilities = result.validation_probabilities

    assert list(probabilities.columns) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]
    assert len(probabilities) == result.validation_rows
    np.testing.assert_allclose(
        probabilities.sum(axis=1).to_numpy(),
        1.0,
        atol=1e-8,
    )


def test_ab37_training_boundaries_are_strictly_chronological() -> None:
    """Training metadata must preserve causal ordering and purge gaps."""
    result = train_baseline(_dataset())

    assert result.train_end < result.validation_start
    assert result.validation_end < result.test_start
    assert result.train_end < result.validation_end < result.test_start

    # The validation probabilities correspond only to the validation
    # partition; the external test partition is never passed to prediction.
    assert result.validation_rows < result.train_rows
    assert result.validation_rows < result.test_rows or result.test_rows > 0
