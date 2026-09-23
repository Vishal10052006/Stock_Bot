"""
Phase 9 model evaluation public API.
"""

from .baselines import (
    ProbabilityBaseline,
    class_prior_probabilities,
    majority_class,
    majority_probabilities,
)
from .effective_sample import (
    EffectiveSampleDiagnostics,
    diagnose_effective_sample,
)
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
from .return_forecast import (
    evaluate_prediction_intervals,
    evaluate_return_forecasts,
    evaluate_return_forecasts_by_column,
)
from .stratified import StratifiedEvaluation, evaluate_by_column

__all__ = [
    "EVALUATION_CLASSES",
    "EvaluationConfig",
    "EvaluationResult",
    "ProbabilityBaseline",
    "class_prior_probabilities",
    "majority_class",
    "majority_probabilities",
    "EffectiveSampleDiagnostics",
    "diagnose_effective_sample",
    "StratifiedEvaluation",
    "evaluate_by_column",
    "evaluate_predictions",
    "expected_calibration_error",
    "multiclass_brier_score",
    "evaluate_training_result",
    "evaluate_return_forecasts",
    "evaluate_return_forecasts_by_column",
    "evaluate_prediction_intervals",
]
