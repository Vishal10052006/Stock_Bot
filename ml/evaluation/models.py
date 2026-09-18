"""
Core models for Phase 9 model evaluation.

Evaluation measures predictive performance on data that was not used
to fit the model.

This layer evaluates classification/probability quality only.
Trading performance belongs to the backtesting layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


EVALUATION_CLASSES: tuple[str, ...] = (
    "LONG_SUCCESS",
    "SHORT_SUCCESS",
    "NO_EDGE",
)


@dataclass(frozen=True)
class EvaluationConfig:
    """
    Configuration for Phase 9 baseline model evaluation.

    All three prediction classes are always evaluated, even when a
    particular metric implementation could omit unused classes.
    """

    classes: tuple[str, ...] = EVALUATION_CLASSES

    def __post_init__(self) -> None:
        """Validate evaluation configuration."""

        if tuple(self.classes) != EVALUATION_CLASSES:
            raise ValueError(
                "classes must use the canonical Phase 9 class order."
            )


@dataclass(frozen=True)
class EvaluationResult:
    """
    Immutable summary of validation-set model performance.

    The result contains classification metrics, probability quality,
    and a confusion matrix.

    These metrics describe predictive performance only. They do not
    represent trading profitability.
    """

    accuracy: float
    balanced_accuracy: float

    macro_precision: float
    macro_recall: float
    macro_f1: float

    log_loss: float

    confusion_matrix: np.ndarray

    sample_count: int
    classes: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate evaluation result invariants."""

        metrics = (
            self.accuracy,
            self.balanced_accuracy,
            self.macro_precision,
            self.macro_recall,
            self.macro_f1,
            self.log_loss,
        )

        if not all(
            np.isfinite(metric)
            for metric in metrics
        ):
            raise ValueError(
                "Evaluation metrics must be finite."
            )

        bounded_metrics = (
            self.accuracy,
            self.balanced_accuracy,
            self.macro_precision,
            self.macro_recall,
            self.macro_f1,
        )

        if not all(
            0.0 <= metric <= 1.0
            for metric in bounded_metrics
        ):
            raise ValueError(
                "Classification metrics must lie in [0, 1]."
            )

        if self.log_loss < 0.0:
            raise ValueError(
                "log_loss must not be negative."
            )

        if self.sample_count <= 0:
            raise ValueError(
                "sample_count must be greater than 0."
            )

        if tuple(self.classes) != EVALUATION_CLASSES:
            raise ValueError(
                "EvaluationResult must use the canonical "
                "Phase 9 class order."
            )

        matrix = np.asarray(
            self.confusion_matrix
        )

        expected_shape = (
            len(EVALUATION_CLASSES),
            len(EVALUATION_CLASSES),
        )

        if matrix.shape != expected_shape:
            raise ValueError(
                "confusion_matrix must have shape "
                f"{expected_shape}."
            )

        if not np.isfinite(
            matrix.astype(float)
        ).all():
            raise ValueError(
                "confusion_matrix must contain finite values."
            )

        if (matrix < 0).any():
            raise ValueError(
                "confusion_matrix must not contain negative values."
            )

        if int(matrix.sum()) != self.sample_count:
            raise ValueError(
                "confusion_matrix total must equal sample_count."
            )
