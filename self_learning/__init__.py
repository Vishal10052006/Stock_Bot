"""Controlled self-learning contract primitives.

The package is intentionally separate from trading execution.  It provides
versioned evidence, experiment, dataset, candidate, validation, promotion,
rollback, and orchestration contracts without granting order authority.
"""

from .contracts import (
    CandidateLifecycle,
    DatasetVersion,
    ExperienceBundle,
    ExperimentLifecycle,
    ExperimentSpec,
    LearningCycleReport,
    LearningEvidence,
    LearningTrigger,
    ModelCandidate,
    PromotionDecision,
    PromotionState,
    ValidationSummary,
)
from .store import AppendOnlyLearningStore
from .dataset import build_dataset_version
from .validation import validate_candidate
from .promotion import PromotionController
from .orchestrator import SelfLearningOrchestrator

__all__ = [
    "AppendOnlyLearningStore",
    "CandidateLifecycle",
    "DatasetVersion",
    "ExperienceBundle",
    "ExperimentLifecycle",
    "ExperimentSpec",
    "LearningCycleReport",
    "LearningEvidence",
    "LearningTrigger",
    "ModelCandidate",
    "PromotionController",
    "PromotionDecision",
    "PromotionState",
    "SelfLearningOrchestrator",
    "ValidationSummary",
    "build_dataset_version",
    "validate_candidate",
]
