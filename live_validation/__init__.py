"""Real-market prediction outcome validation.

This package links prediction-only observations to later, fully resolved
Phase 7 outcomes without granting trading or broker authority.
"""

from .bridge import LivePredictionValidationBridge
from .evaluator import LivePredictionEvaluator
from .journal import LiveValidationJournal
from .models import (
    LiveOutcome,
    LivePrediction,
    LivePredictionReport,
    OutcomeStatus,
)
from .resolver import LiveOutcomeResolver

__all__ = [
    "LiveOutcome",
    "LiveOutcomeResolver",
    "LivePrediction",
    "LivePredictionEvaluator",
    "LivePredictionReport",
    "LivePredictionValidationBridge",
    "LiveValidationJournal",
    "OutcomeStatus",
]
