"""Controlled STOCK_BOT self-learning package.

The package composes the existing Phase 16-20 evidence and governance
boundaries without granting broker or hard-risk authority.
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
from .experience import (
    ExperienceAudit,
    ExperienceContractError,
    audit_journal_linkage,
    build_trade_experience,
)
from .dataset_store import DatasetManifestStore
from .experiment_store import ExperimentRegistry
from .cycle_store import LearningCycleStore
from .retraining import ControlledRetrainer, RetrainingResult
from .validation import ValidationBundle, ValidationOrchestrator
from .promotion import PromotionGate
from .champion import ChampionChallenger, RollbackPlan, build_rollback_plan
from .drift import DriftInvestigation, DriftInvestigator
from .orchestrator import SelfLearningEngine, SelfLearningRun

__all__ = [
    "ChampionChallenger",
    "ChampionRecord",
    "ControlledRetrainer",
    "DatasetManifestStore",
    "DatasetVersion",
    "DriftInvestigation",
    "DriftInvestigator",
    "ErrorClass",
    "ExperienceAudit",
    "ExperienceContractError",
    "ExperimentLineage",
    "ExperimentRegistry",
    "FailureClass",
    "LearningConfig",
    "LearningCycle",
    "LearningCycleStore",
    "LearningDecision",
    "LearningEngine",
    "LearningExperience",
    "LearningPattern",
    "LearningReport",
    "LearningState",
    "PromotionGate",
    "PromotionReview",
    "RetrainingResult",
    "RollbackPlan",
    "SelfLearningEngine",
    "SelfLearningRun",
    "TradeOutcomeContext",
    "ValidationBundle",
    "ValidationEvidence",
    "ValidationOrchestrator",
    "audit_journal_linkage",
    "build_rollback_plan",
    "build_trade_experience",
]
