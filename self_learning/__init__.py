"""Controlled self-learning package exports."""

from .candidate_lifecycle import CandidateLifecycleController, allowed_transitions
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
from .orchestrator import LearningRunResult, SelfLearningOrchestrator
from .promotion import PromotionController
from .provenance import build_phase9_dataset_version
from .retraining import RetrainingResult, retrain_candidate
from .real_dataset import (
    DatasetDiagnostics,
    Phase9DatasetError,
    SnapshotOverlap,
    compare_snapshot_overlap,
    discover_phase9_snapshots,
    inspect_phase9_snapshot,
    load_phase9_dataset,
    validate_snapshot_set,
)
from .store import AppendOnlyLearningStore, DuplicateArtifactError
from .validation import ValidationPolicy, validate_candidate
from .validation_adapter import summarize_artifact, validate_dataset_boundary
from .validation_orchestrator import ValidationOrchestrator, ValidationRun

__all__ = [
    "AppendOnlyLearningStore",
    "CandidateLifecycleController",
    "CandidateLifecycle",
    "ChampionState",
    "ChampionStateStore",
    "DatasetVersion",
    "DatasetDiagnostics",
    "Phase9DatasetError",
    "SnapshotOverlap",
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
    "PromotionController",
    "PromotionDecision",
    "PromotionState",
    "RetrainingResult",
    "SelfLearningOrchestrator",
    "ValidationOrchestrator",
    "ValidationPolicy",
    "ValidationRun",
    "ValidationSummary",
    "build_dataset_version",
    "build_phase9_dataset_version",
    "compare_snapshot_overlap",
    "discover_phase9_snapshots",
    "inspect_phase9_snapshot",
    "load_phase9_dataset",
    "validate_snapshot_set",
    "dataframe_fingerprint",
    "retrain_candidate",
    "summarize_artifact",
    "validate_candidate",
    "validate_dataset_boundary",
    "allowed_transitions",
]
