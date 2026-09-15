"""
Phase 7 prediction-target labeling package.
"""

from .engine import (
    label_candidate,
    label_candidates,
    label_decision,
)
from .models import (
    AmbiguousOutcomePolicy,
    DecisionLabelingOutcome,
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
    "DecisionLabelingOutcome",
    "label_decision",
]
