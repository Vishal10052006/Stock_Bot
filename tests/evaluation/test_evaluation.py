"""
Tests for Phase 9 model evaluation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.evaluation import EVALUATION_CLASSES
from ml.evaluation.metrics import evaluate_predictions


def make_probabilities() -> pd.DataFrame:
    """Create deterministic probabilities in STOCK BOT class order."""

    return pd.DataFrame(
        [
            [0.90, 0.05, 0.05],
            [0.05, 0.90, 0.05],
            [0.05, 0.05, 0.90],
            [0.80, 0.10, 0.10],
            [0.10, 0.80, 0.10],
            [0.10, 0.10, 0.80],
        ],
        columns=EVALUATION_CLASSES,
    )


def make_labels() -> np.ndarray:
    """Create matching deterministic labels."""

    return np.array(
        [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        ]
    )


def test_perfect_predictions_have_perfect_classification_metrics():
    """Correct predictions should achieve perfect classification metrics."""

    metrics = evaluate_predictions(
        make_labels(),
        make_probabilities(),
    )

    assert metrics["accuracy"] == pytest.approx(1.0)
    assert metrics["balanced_accuracy"] == pytest.approx(1.0)
    assert metrics["macro_precision"] == pytest.approx(1.0)
    assert metrics["macro_recall"] == pytest.approx(1.0)
    assert metrics["macro_f1"] == pytest.approx(1.0)


def test_probability_columns_use_canonical_class_order():
    """
    Probability columns must retain LONG, SHORT, NO_EDGE semantics.

    This specifically guards against sklearn class-order mismatches.
    """

    metrics = evaluate_predictions(
        make_labels(),
        make_probabilities(),
    )

    assert metrics["log_loss"] == pytest.approx(
        0.164252,
        abs=1e-6,
    )


def test_confusion_matrix_uses_canonical_class_order():
    """Confusion matrix rows/columns follow the canonical class order."""

    metrics = evaluate_predictions(
        make_labels(),
        make_probabilities(),
    )

    expected = np.diag([2, 2, 2])

    np.testing.assert_array_equal(
        metrics["confusion_matrix"],
        expected,
    )


def test_probability_rows_must_sum_to_one():
    """Invalid probability distributions must be rejected."""

    probabilities = make_probabilities()
    probabilities.iloc[0, 0] = 0.50

    with pytest.raises(ValueError, match="sum to 1"):
        evaluate_predictions(
            make_labels(),
            probabilities,
        )


def test_probability_values_must_be_finite():
    """NaN/inf probabilities must be rejected."""

    probabilities = make_probabilities()
    probabilities.iloc[0, 0] = np.nan
    probabilities.iloc[0, 1] = np.nan
    probabilities.iloc[0, 2] = np.nan

    with pytest.raises(ValueError, match="finite"):
        evaluate_predictions(
            make_labels(),
            probabilities,
        )


def test_probability_values_must_be_between_zero_and_one():
    """Probabilities outside [0, 1] must be rejected."""

    probabilities = make_probabilities()
    probabilities.iloc[0, 0] = 1.1

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        evaluate_predictions(
            make_labels(),
            probabilities,
        )


def test_probability_columns_must_match_canonical_order():
    """Reordered probability columns must be rejected."""

    probabilities = make_probabilities()[
        [
            "LONG_SUCCESS",
            "NO_EDGE",
            "SHORT_SUCCESS",
        ]
    ]

    with pytest.raises(ValueError, match="canonical"):
        evaluate_predictions(
            make_labels(),
            probabilities,
        )


def test_invalid_labels_are_rejected():
    """Unknown target classes must be rejected."""

    labels = make_labels()
    labels[0] = "INVALID"

    with pytest.raises(ValueError, match="invalid"):
        evaluate_predictions(
            labels,
            make_probabilities(),
        )


def test_empty_labels_are_rejected():
    """Evaluation requires at least one observation."""

    with pytest.raises(ValueError, match="at least one"):
        evaluate_predictions(
            np.array([]),
            pd.DataFrame(
                columns=EVALUATION_CLASSES
            ),
        )


def test_y_true_and_probability_lengths_must_match():
    """Labels and probability rows must represent the same observations."""

    labels = make_labels()[:-1]

    with pytest.raises(ValueError):
        evaluate_predictions(
            labels,
            make_probabilities(),
        )
