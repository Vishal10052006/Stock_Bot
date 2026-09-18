"""Tests for Phase 9 probability calibration."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import MODEL_CLASSES


def test_isotonic_calibrator_preserves_probability_contract() -> None:
    """Calibrated rows must remain finite and sum to one."""
    probabilities = pd.DataFrame(
        [
            [0.80, 0.10, 0.10],
            [0.70, 0.20, 0.10],
            [0.10, 0.80, 0.10],
            [0.20, 0.70, 0.10],
            [0.10, 0.10, 0.80],
            [0.20, 0.10, 0.70],
        ],
        columns=list(MODEL_CLASSES),
    )
    labels = pd.Series(
        [
            "LONG_SUCCESS",
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
            "NO_EDGE",
        ]
    )

    calibrator = IsotonicProbabilityCalibrator().fit(
        probabilities,
        labels,
    )
    result = calibrator.transform(probabilities)

    assert calibrator.is_fitted is True
    assert tuple(result.columns) == MODEL_CLASSES
    assert np.isfinite(result.to_numpy()).all()
    assert np.allclose(result.sum(axis=1), 1.0)


def test_calibrator_rejects_single_class_calibration_data() -> None:
    """Calibration must not fit a degenerate one-vs-rest target."""
    probabilities = pd.DataFrame(
        np.tile([0.8, 0.1, 0.1], (6, 1)),
        columns=list(MODEL_CLASSES),
    )
    labels = pd.Series(["LONG_SUCCESS"] * 6)

    with pytest.raises(ValueError, match="positive and negative"):
        IsotonicProbabilityCalibrator().fit(probabilities, labels)
