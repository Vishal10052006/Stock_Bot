"""Controlled self-learning package exports."""

from .champion import ChampionState, ChampionStateStore
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
from .dataset import build_dataset_version, dataframe_fingerprint
from .experiments import ExperimentArtifact, ExperimentRegistry
from .promotion import PromotionController
from .retraining import RetrainingResult, retrain_candidate
from .store import AppendOnlyLearningStore, DuplicateArtifactError
from .validation import ValidationPolicy, validate_candidate
from .orchestrator import LearningRunResult, SelfLearningOrchestrator

__all__ = [
    "AppendOnlyLearningStore",
    "CandidateLifecycle",
    "ChampionState",
    "ChampionStateStore",
    "DatasetVersion",
    "DuplicateArtifactError",
    "ExperienceBundle",
    "ExperimentArtifact",
    "ExperimentLifecycle",
    "ExperimentRegistry",
    "ExperimentSpec",
    "LearningCycleReport",
    "LearningEvidence",
    "LearningRunResult",
    "LearningTrigger",
    "ModelCandidate",
    "ModelCandidate",
    "ModelCandidate",
    "PromotionController",
    "PromotionDecision",
    "PromotionState",
    "RetrainingResult",
    "SelfLearningOrchestrator",
    "ValidationPolicy",
    "ValidationSummary",
    "build_dataset_version",
    "dataframe_fingerprint",
    "retrain_candidate",
    "validate_candidate",
]
