"""
Phase 9 classification and probability metrics.

This module evaluates predictive quality only. It does not evaluate
trading profitability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    log_loss,
    precision_score,
    recall_score,
    f1_score,
)

from .models import EVALUATION_CLASSES


def evaluate_predictions(
    y_true: pd.Series | np.ndarray,
    probabilities: pd.DataFrame,
) -> dict[str, object]:
    """
    Calculate Phase 9 validation metrics.

    Parameters
    ----------
    y_true:
        Actual decision-level labels.

    probabilities:
        Predicted probabilities in canonical class order.

    Returns
    -------
    dict
        Classification metrics and confusion matrix.

    Notes
    -----
    `probabilities` must already represent predictions from a model
    that was fitted without using the evaluation observations.
    """

    y_array = _validate_y_true(y_true)
    probability_array = _validate_probabilities(probabilities)

    if len(y_array) != len(probability_array):
        raise ValueError(
            "y_true and probabilities must contain the same number "
            "of observations."
        )

    predictions = probabilities.idxmax(
        axis=1
    ).to_numpy()

    labels = list(EVALUATION_CLASSES)

    return {
        "accuracy": float(
            accuracy_score(
                y_array,
                predictions,
            )
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(
                y_array,
                predictions,
            )
        ),
        "macro_precision": float(
            precision_score(
                y_array,
                predictions,
                labels=labels,
                average="macro",
                zero_division=0,
            )
        ),
        "macro_recall": float(
            recall_score(
                y_array,
                predictions,
                labels=labels,
                average="macro",
                zero_division=0,
            )
        ),
        "macro_f1": float(
            f1_score(
                y_array,
                predictions,
                labels=labels,
                average="macro",
                zero_division=0,
            )
        ),
        "log_loss": float(
            log_loss(
                y_array,
                probability_array[
                    :,
                    [
                        EVALUATION_CLASSES.index("LONG_SUCCESS"),
                        EVALUATION_CLASSES.index("NO_EDGE"),
                        EVALUATION_CLASSES.index("SHORT_SUCCESS"),
                    ],
                ],
                labels=[
                    "LONG_SUCCESS",
                    "NO_EDGE",
                    "SHORT_SUCCESS",
                ],
            )
        ),
        "confusion_matrix": confusion_matrix(
            y_array,
            predictions,
            labels=labels,
        ).tolist(),
    }


def multiclass_brier_score(
    y_true: pd.Series | np.ndarray,
    probabilities: pd.DataFrame,
) -> float:
    """Calculate the multiclass Brier score for probability quality."""
    y_array = _validate_y_true(y_true)
    values = _validate_probabilities(probabilities)

    if len(y_array) != len(values):
        raise ValueError("y_true and probabilities must contain the same number of observations.")

    targets = np.zeros_like(values)
    for index, label in enumerate(EVALUATION_CLASSES):
        targets[:, index] = (y_array == label).astype(float)

    return float(np.mean(np.sum((values - targets) ** 2, axis=1)))


def expected_calibration_error(
    y_true: pd.Series | np.ndarray,
    probabilities: pd.DataFrame,
    bins: int = 10,
) -> float:
    """Calculate confidence-based expected calibration error (ECE)."""
    if bins <= 0:
        raise ValueError("bins must be greater than 0.")

    y_array = _validate_y_true(y_true)
    values = _validate_probabilities(probabilities)

    if len(y_array) != len(values):
        raise ValueError("y_true and probabilities must contain the same number of observations.")

    confidence = values.max(axis=1)
    predictions = values.argmax(axis=1)
    class_names = np.asarray(EVALUATION_CLASSES)
    correct = (class_names[predictions] == y_array).astype(float)

    edges = np.linspace(0.0, 1.0, bins + 1)
    error = 0.0

    for lower, upper in zip(edges[:-1], edges[1:]):
        mask = (confidence >= lower) & (
            confidence < upper if upper < 1.0 else confidence <= upper
        )
        count = int(mask.sum())
        if count == 0:
            continue
        error += (count / len(values)) * abs(
            float(correct[mask].mean()) - float(confidence[mask].mean())
        )

    return float(error)


def _validate_y_true(
    y_true: pd.Series | np.ndarray,
) -> np.ndarray:
    """Validate actual labels."""

    if isinstance(y_true, pd.Series):
        values = y_true.to_numpy()
    elif isinstance(y_true, np.ndarray):
        values = y_true
    else:
        raise TypeError(
            "y_true must be a pandas Series or numpy ndarray."
        )

    if values.ndim != 1:
        raise ValueError(
            "y_true must be one-dimensional."
        )

    if len(values) == 0:
        raise ValueError(
            "y_true must contain at least one value."
        )

    values = values.astype(str)

    invalid = set(values) - set(EVALUATION_CLASSES)

    if invalid:
        raise ValueError(
            "y_true contains invalid prediction labels: "
            f"{sorted(invalid)}"
        )

    return values


def _validate_probabilities(
    probabilities: pd.DataFrame,
) -> np.ndarray:
    """Validate canonical probability output."""

    if not isinstance(
        probabilities,
        pd.DataFrame,
    ):
        raise TypeError(
            "probabilities must be a pandas DataFrame."
        )

    if list(probabilities.columns) != list(
        EVALUATION_CLASSES
    ):
        raise ValueError(
            "probabilities must use the canonical Phase 9 "
            "class order."
        )

    if probabilities.empty:
        raise ValueError(
            "probabilities must contain at least one row."
        )

    values = probabilities.to_numpy(
        dtype=float
    )

    if not np.isfinite(values).all():
        raise ValueError(
            "probabilities must contain only finite values."
        )

    if (values < 0.0).any() or (values > 1.0).any():
        raise ValueError(
            "probabilities must lie in [0, 1]."
        )

    if not np.allclose(
        values.sum(axis=1),
        1.0,
        atol=1e-8,
    ):
        raise ValueError(
            "probability rows must sum to 1."
        )

    return values
