"""Controlled STOCK_BOT self-learning package.

The public API composes the existing Phase 16-19 learning evidence with
versioned experiment, retraining, validation, promotion, and rollback
contracts. It never grants broker or hard-risk authority.
"""

from .engine import LearningEngine
from .models import (
    ErrorClass,
    LearningConfig,
    LearningExperience,
    LearningPattern,
    LearningReport,
)
from .self_learning_models import (
    ChampionRecord,
    DatasetVersion,
    ExperimentLineage,
    FailureClass,
    LearningCycle,
    LearningDecision,
    LearningState,
    PromotionReview,
    TradeOutcomeContext,
    ValidationEvidence,
)

__all__ = [
    "ChampionRecord",
    "DatasetVersion",
    "ErrorClass",
    "ExperimentLineage",
    "FailureClass",
    "LearningConfig",
    "LearningCycle",
    "LearningDecision",
    "LearningEngine",
    "LearningExperience",
    "LearningPattern",
    "LearningReport",
    "LearningState",
    "PromotionReview",
    "TradeOutcomeContext",
    "ValidationEvidence",
]
