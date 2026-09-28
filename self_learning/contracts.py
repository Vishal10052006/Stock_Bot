"""Immutable contracts for the controlled Self-Learning Engine.

References:
    - STOCK_BOT Self-Learning Engine master specification.
    - Existing Phase-16/17/18/19/20 repository contracts.

This module intentionally contains no trading authority.  Learning may propose
and evaluate changes, but Strategy, Risk, Safety, and Execution remain outside
this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping, Sequence


def _canonical(value: Any) -> Any:
    """Convert supported values into deterministic JSON-compatible data."""
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical(item) for item in value)
    if isinstance(value, Enum):
        return value.value
    return value


def _fingerprint(value: Any) -> str:
    """Return a stable SHA-256 identity for a JSON-compatible object."""
    payload = json.dumps(
        _canonical(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Deep-freeze mapping metadata so records remain immutable."""
    value = value or {}
    return MappingProxyType(
        {
            str(key): _freeze_value(child)
            for key, child in value.items()
        }
    )


def _freeze_value(value: Any) -> Any:
    """Recursively freeze JSON-like metadata."""
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return value


class LearningTrigger(str, Enum):
    """Evidence source that may initiate learning investigation."""

    NEW_OUTCOMES = "NEW_OUTCOMES"
    ERROR_PATTERN = "ERROR_PATTERN"
    MODEL_DRIFT = "MODEL_DRIFT"
    FEATURE_DRIFT = "FEATURE_DRIFT"
    PERFORMANCE_DRIFT = "PERFORMANCE_DRIFT"
    EXECUTION_DRIFT = "EXECUTION_DRIFT"
    MANUAL_RESEARCH = "MANUAL_RESEARCH"


class ExperimentLifecycle(str, Enum):
    """Research lifecycle for a controlled experiment."""

    PROPOSED = "PROPOSED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    OOS = "OOS"
    WALK_FORWARD = "WALK_FORWARD"
    PAPER = "PAPER"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class CandidateLifecycle(str, Enum):
    """Candidate model/component lifecycle."""

    CANDIDATE = "CANDIDATE"
    VALIDATING = "VALIDATING"
    PAPER = "PAPER"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class CandidateLifecycleTransition(str, Enum):
    """Lifecycle transitions accepted by the candidate controller."""

    START_VALIDATION = "START_VALIDATION"
    ENTER_PAPER = "ENTER_PAPER"
    REQUEST_PROMOTION_REVIEW = "REQUEST_PROMOTION_REVIEW"
    PROMOTE = "PROMOTE"
    REJECT = "REJECT"
    RETIRE = "RETIRE"


class PromotionState(str, Enum):
    """Controlled champion/challenger transition states."""

    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    PROMOTED = "PROMOTED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class ExperienceBundle:
    """Immutable bridge from the authoritative Phase-16/17 evidence."""

    trade_ids: tuple[str, ...]
    experience_fingerprints: tuple[str, ...]
    learning_fingerprints: tuple[str, ...]
    outcome_count: int
    linked_decision_count: int
    source_journal_fingerprint: str
    source_analysis_fingerprint: str
    created_at: str

    def __post_init__(self) -> None:
        if self.outcome_count < 0 or self.linked_decision_count < 0:
            raise ValueError("experience counts must be non-negative")
        if len(self.trade_ids) != len(set(self.trade_ids)):
            raise ValueError("trade_ids must be unique")
        if not self.source_journal_fingerprint or len(self.source_journal_fingerprint) != 64:
            raise ValueError("source_journal_fingerprint must be SHA-256")
        if not self.source_analysis_fingerprint or len(self.source_analysis_fingerprint) != 64:
            raise ValueError("source_analysis_fingerprint must be SHA-256")
        if not self.created_at.strip():
            raise ValueError("created_at must not be empty")

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    """One evidence-backed learning observation, never a trade instruction."""

    evidence_id: str
    pattern: str
    error_class: str
    source_trade_ids: tuple[str, ...]
    evidence_count: int
    population_count: int
    occurrence_rate: float
    confidence: float
    average_reward: float
    rationale: str
    conditions: tuple[str, ...] = ()
    trigger: LearningTrigger = LearningTrigger.ERROR_PATTERN
    source_experience_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty")
        if not self.pattern.strip() or not self.error_class.strip():
            raise ValueError("pattern and error_class must not be empty")
        if self.evidence_count < 1:
            raise ValueError("evidence_count must be positive")
        if self.population_count < self.evidence_count:
            raise ValueError("population_count must be >= evidence_count")
        if not 0.0 <= self.occurrence_rate <= 1.0:
            raise ValueError("occurrence_rate must be in [0, 1]")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if not isfinite(float(self.average_reward)):
            raise ValueError("average_reward must be finite")
        if not self.source_trade_ids:
            raise ValueError("source_trade_ids must not be empty")
        if len(self.source_trade_ids) != self.evidence_count:
            raise ValueError("source_trade_ids count must equal evidence_count")
        if not self.rationale.strip():
            raise ValueError("rationale must not be empty")
        if self.source_experience_fingerprint and len(self.source_experience_fingerprint) != 64:
            raise ValueError("source_experience_fingerprint must be SHA-256")

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class ExperimentSpec:
    """Immutable experiment specification with one primary change."""

    experiment_id: str
    research_question: str
    hypothesis: str
    null_hypothesis: str
    failure_criterion: str
    dataset_version: str
    code_version: str
    feature_version: str
    label_version: str
    model_version: str
    strategy_version: str
    risk_version: str
    execution_version: str
    period_start: str
    period_end: str
    symbols: tuple[str, ...]
    method: str
    changed_component: str
    changed_parameter: str
    baseline_fingerprints: Mapping[str, str]
    trigger_evidence_fingerprint: str = ""
    parent_experiment_id: str | None = None
    lifecycle: ExperimentLifecycle = ExperimentLifecycle.PROPOSED

    def __post_init__(self) -> None:
        text_fields = (
            "experiment_id",
            "research_question",
            "hypothesis",
            "null_hypothesis",
            "failure_criterion",
            "dataset_version",
            "code_version",
            "feature_version",
            "label_version",
            "model_version",
            "strategy_version",
            "risk_version",
            "execution_version",
            "period_start",
            "period_end",
            "method",
            "changed_component",
            "changed_parameter",
        )
        for field_name in text_fields:
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be empty")
        if not self.symbols:
            raise ValueError("symbols must not be empty")
        if not self.changed_component.strip() or not self.changed_parameter.strip():
            raise ValueError("exactly one primary change must be declared")
        if self.trigger_evidence_fingerprint and len(self.trigger_evidence_fingerprint) != 64:
            raise ValueError("trigger_evidence_fingerprint must be SHA-256")
        object.__setattr__(self, "baseline_fingerprints", _freeze_mapping(self.baseline_fingerprints))

    @property
    def fingerprint(self) -> str:
        """Return deterministic experiment identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """Immutable dataset provenance record."""

    dataset_version: str
    source: str
    creation_timestamp: str
    symbols: tuple[str, ...]
    period_start: str
    period_end: str
    row_count: int
    label_distribution: Mapping[str, int]
    feature_schema_version: str
    label_definition_version: str
    source_fingerprints: tuple[str, ...]
    known_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_version.strip() or not self.source.strip():
            raise ValueError("dataset_version and source must not be empty")
        if self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        if not self.symbols:
            raise ValueError("symbols must not be empty")
        if not self.feature_schema_version.strip() or not self.label_definition_version.strip():
            raise ValueError("feature and label versions are required")
        if any(len(item) != 64 for item in self.source_fingerprints):
            raise ValueError("source_fingerprints must be SHA-256 identities")
        if any(int(count) < 0 for count in self.label_distribution.values()):
            raise ValueError("label counts must be non-negative")
        object.__setattr__(self, "label_distribution", _freeze_mapping(self.label_distribution))

    @property
    def fingerprint(self) -> str:
        """Return deterministic dataset identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Neutral, machine-readable validation outcome."""

    stage: str
    valid: bool
    observations: int
    metrics: Mapping[str, float]
    limitations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    artifact_fingerprints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.stage.strip():
            raise ValueError("stage must not be empty")
        if self.observations < 0:
            raise ValueError("observations must be non-negative")
        for key, value in self.metrics.items():
            if not isinstance(key, str):
                raise TypeError("metric names must be strings")
            if not isfinite(float(value)):
                raise ValueError("validation metrics must be finite")
        if any(len(item) != 64 for item in self.artifact_fingerprints):
            raise ValueError("artifact_fingerprints must be SHA-256 identities")
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))

    @property
    def fingerprint(self) -> str:
        """Return deterministic validation identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    """Immutable candidate model/component with explicit provenance."""

    candidate_id: str
    candidate_version: str
    candidate_type: str
    lifecycle: CandidateLifecycle
    dataset_version: str
    feature_version: str
    label_version: str
    source_experiment_id: str
    source_experiment_fingerprint: str
    artifact_fingerprint: str
    evaluation_fingerprint: str
    lineage_id: str
    metrics: Mapping[str, float]
    parent_model_version: str
    strategy_version: str
    created_at: str

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "candidate_version",
            "candidate_type",
            "dataset_version",
            "feature_version",
            "label_version",
            "source_experiment_id",
            "parent_model_version",
            "strategy_version",
            "created_at",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")
        for name in (
            "source_experiment_fingerprint",
            "artifact_fingerprint",
            "evaluation_fingerprint",
            "lineage_id",
        ):
            value = getattr(self, name)
            if len(value) != 64:
                raise ValueError(f"{name} must be SHA-256")
        for value in self.metrics.values():
            if not isfinite(float(value)):
                raise ValueError("candidate metrics must be finite")
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))

    @property
    def fingerprint(self) -> str:
        """Return deterministic candidate identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    """Immutable decision record for champion/challenger governance."""

    candidate_id: str
    candidate_fingerprint: str
    champion_version: str
    challenger_version: str
    state: PromotionState
    reasons: tuple[str, ...]
    validation_fingerprints: tuple[str, ...]
    approval_reference: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be empty")
        if len(self.candidate_fingerprint) != 64:
            raise ValueError("candidate_fingerprint must be SHA-256")
        if not self.champion_version.strip() or not self.challenger_version.strip():
            raise ValueError("champion/challenger versions are required")
        if any(len(item) != 64 for item in self.validation_fingerprints):
            raise ValueError("validation_fingerprints must be SHA-256")
        if self.state is PromotionState.PROMOTED and not self.approval_reference.strip():
            raise ValueError("PROMOTED requires approval_reference")
        if self.state is PromotionState.PROMOTED and not self.created_at.strip():
            raise ValueError("PROMOTED requires created_at")

    @property
    def fingerprint(self) -> str:
        """Return deterministic promotion identity."""
        return _fingerprint(self)


@dataclass(frozen=True, slots=True)
class LearningCycleReport:
    """Immutable summary of one end-to-end learning cycle."""

    cycle_id: str
    trigger: LearningTrigger
    experience_fingerprint: str
    evidence_fingerprints: tuple[str, ...]
    experiment_fingerprint: str | None
    validation_fingerprints: tuple[str, ...]
    promotion_fingerprint: str | None
    status: str
    next_action: str

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ValueError("cycle_id must not be empty")
        if len(self.experience_fingerprint) != 64:
            raise ValueError("experience_fingerprint must be SHA-256")
        if any(len(item) != 64 for item in self.evidence_fingerprints):
            raise ValueError("evidence_fingerprints must be SHA-256")
        if self.experiment_fingerprint is not None and len(self.experiment_fingerprint) != 64:
            raise ValueError("experiment_fingerprint must be SHA-256")
        if any(len(item) != 64 for item in self.validation_fingerprints):
            raise ValueError("validation_fingerprints must be SHA-256")
        if self.promotion_fingerprint is not None and len(self.promotion_fingerprint) != 64:
            raise ValueError("promotion_fingerprint must be SHA-256")
        if not self.status.strip() or not self.next_action.strip():
            raise ValueError("status and next_action must not be empty")

    @property
    def fingerprint(self) -> str:
        """Return deterministic cycle identity."""
        return _fingerprint(self)
