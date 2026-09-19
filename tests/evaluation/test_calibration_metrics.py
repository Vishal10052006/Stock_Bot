"""Tests for Phase 9 probability-quality metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.evaluation.metrics import (
    expected_calibration_error,
    multiclass_brier_score,
)
from ml.models.logistic import MODEL_CLASSES


def make_inputs() -> tuple[pd.Series, pd.DataFrame]:
    """Create deterministic probability predictions."""
    labels = pd.Series(
        [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
            "LONG_SUCCESS",
        ]
    )
    probabilities = pd.DataFrame(
        [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.1, 0.8],
            [0.7, 0.2, 0.1],
        ],
        columns=list(MODEL_CLASSES),
    )
    return labels, probabilities


def test_multiclass_brier_score_is_finite_and_non_negative() -> None:
    """Brier score must be a valid non-negative probability metric."""
    labels, probabilities = make_inputs()
    score = multiclass_brier_score(labels, probabilities)

    assert np.isfinite(score)
    assert score >= 0.0


def test_expected_calibration_error_is_bounded() -> None:
    """ECE must lie between zero and one."""
    labels, probabilities = make_inputs()
    score = expected_calibration_error(labels, probabilities)

    assert np.isfinite(score)
    assert 0.0 <= score <= 1.0


def test_expected_calibration_error_rejects_invalid_bin_count() -> None:
    """Invalid calibration bin counts must fail explicitly."""
    labels, probabilities = make_inputs()

    with pytest.raises(ValueError, match="bins"):
        expected_calibration_error(labels, probabilities, bins=0)
