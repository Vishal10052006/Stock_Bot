"""
Phase 9 model evaluation orchestration.

The evaluator measures a fitted TrainingResult against the labels from
the corresponding validation partition.

The test partition is never evaluated here.
"""

from __future__ import annotations

from ml.datasets.models import TrainingDataset
from ml.training.models import TrainingResult

from .metrics import evaluate_predictions
from .models import EvaluationConfig, EvaluationResult


def evaluate_training_result(
    training_result: TrainingResult,
    validation_dataset: TrainingDataset,
    config: EvaluationConfig | None = None,
) -> EvaluationResult:
    """
    Evaluate a fitted Phase 9 training result on validation data.

    Parameters
    ----------
    training_result:
        Result produced by ``train_baseline``.

    validation_dataset:
        The validation partition corresponding to the training result.

    config:
        Optional evaluation configuration.

    Returns
    -------
    EvaluationResult
        Validation classification and probability metrics.

    Notes
    -----
    Only validation labels and validation probabilities are consumed.
    The test partition is deliberately unavailable to this evaluator.
    """

    if config is None:
        config = EvaluationConfig()

    if not isinstance(
        training_result,
        TrainingResult,
    ):
        raise TypeError(
            "training_result must be a TrainingResult."
        )

    if not isinstance(
        validation_dataset,
        TrainingDataset,
    ):
        raise TypeError(
            "validation_dataset must be a TrainingDataset."
        )

    if not training_result.model.is_fitted:
        raise ValueError(
            "training_result.model must be fitted."
        )

    if not training_result.preprocessor.is_fitted:
        raise ValueError(
            "training_result.preprocessor must be fitted."
        )

    if (
        training_result.validation_rows
        != len(validation_dataset.data)
    ):
        raise ValueError(
            "validation_dataset row count must match "
            "training_result.validation_rows."
        )

    probabilities = (
        training_result.validation_probabilities
    )

    if len(probabilities) != len(
        validation_dataset.data
    ):
        raise ValueError(
            "Validation probability rows must match "
            "validation dataset rows."
        )

    metrics = evaluate_predictions(
        validation_dataset.y,
        probabilities,
    )

    return EvaluationResult(
        accuracy=metrics["accuracy"],
        balanced_accuracy=metrics[
            "balanced_accuracy"
        ],
        macro_precision=metrics[
            "macro_precision"
        ],
        macro_recall=metrics[
            "macro_recall"
        ],
        macro_f1=metrics["macro_f1"],
        log_loss=metrics["log_loss"],
        confusion_matrix=metrics[
            "confusion_matrix"
        ],
        sample_count=len(validation_dataset.data),
        classes=config.classes,
    )
