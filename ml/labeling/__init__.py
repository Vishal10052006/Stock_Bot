"""
Phase 7 prediction-target labeling package.
"""

from .engine import label_candidate, label_candidates
from .models import (
    AmbiguousOutcomePolicy,
    LabelingConfig,
    LabelingOutcome,
    PredictionLabel,
    TradeCandidate,
    TradeDirection,
)
from .validation import (
    validate_candidate_against_candles,
    validate_candle_frame,
    validate_labeling_output,
)

__all__ = [
    "AmbiguousOutcomePolicy",
    "LabelingConfig",
    "LabelingOutcome",
    "PredictionLabel",
    "TradeCandidate",
    "TradeDirection",
    "label_candidate",
    "label_candidates",
    "validate_candidate_against_candles",
    "validate_candle_frame",
    "validate_labeling_output",
]