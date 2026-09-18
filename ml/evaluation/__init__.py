"""
Phase 9 model evaluation public API.
"""

from .evaluator import evaluate_training_result
from .metrics import (
    evaluate_predictions,
    expected_calibration_error,
    multiclass_brier_score,
)
from .models import (
    EVALUATION_CLASSES,
    EvaluationConfig,
    EvaluationResult,
)

__all__ = [
    "EVALUATION_CLASSES",
    "EvaluationConfig",
    "EvaluationResult",
    "evaluate_predictions",
    "expected_calibration_error",
    "multiclass_brier_score",
    "evaluate_training_result",
]
