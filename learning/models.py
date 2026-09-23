"""AB-47 Phase-18 trade-outcome learning contracts.

Phase 18 converts observed trading outcomes into evidence-backed learning
experiences. It never mutates a model or strategy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class LearningPattern(str, Enum):
    LOSS = "LOSS"
    WIN = "WIN"
    LARGE_MAE = "LARGE_MAE"
    LOW_MFE = "LOW_MFE"
    COST_DRAG = "COST_DRAG"
    REGIME_LOSS_CLUSTER = "REGIME_LOSS_CLUSTER"
    LOW_RVOL_SIDEWAYS_BREAKOUT = "LOW_RVOL_SIDEWAYS_BREAKOUT"
    HIGH_CONFIDENCE_FALSE_SIGNAL = "HIGH_CONFIDENCE_FALSE_SIGNAL"
    OPENING_WINDOW_LOSS = "OPENING_WINDOW_LOSS"
    CONSECUTIVE_LOSS_STREAK = "CONSECUTIVE_LOSS_STREAK"


class ErrorClass(str, Enum):
    OUTCOME_LOSS = "OUTCOME_LOSS"
    POSITIVE_OUTCOME = "POSITIVE_OUTCOME"
    LARGE_ADVERSE_EXCURSION = "LARGE_ADVERSE_EXCURSION"
    LOW_FAVORABLE_EXCURSION = "LOW_FAVORABLE_EXCURSION"
    EXECUTION_COST_DRAG = "EXECUTION_COST_DRAG"
    CONTEXT_LOSS_CLUSTER = "CONTEXT_LOSS_CLUSTER"
    HIGH_CONFIDENCE_FAILURE = "HIGH_CONFIDENCE_FAILURE"
    SEQUENCE_DETERIORATION = "SEQUENCE_DETERIORATION"


@dataclass(frozen=True, slots=True)
class LearningExperience:
    """One evidence-backed observation, not a model-change instruction."""

    pattern: LearningPattern
    error_class: ErrorClass = ErrorClass.OUTCOME_LOSS
    symbol: str | None = None
    evidence_count: int = 1
    population_count: int = 1
    occurrence_rate: float = 1.0
    confidence: float = 0.0
    average_reward: float = 0.0
    total_reward: float = 0.0
    source_trade_ids: tuple[str, ...] = ()
    rationale: str = "Observable trading outcome evidence."

    def __post_init__(self) -> None:
        if self.evidence_count < 1:
            raise ValueError("evidence_count must be at least 1")
        if self.population_count < self.evidence_count:
            raise ValueError("population_count must be >= evidence_count")
        if not 0 <= self.occurrence_rate <= 1:
            raise ValueError("occurrence_rate must be between 0 and 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if len(self.source_trade_ids) != self.evidence_count:
            raise ValueError("source_trade_ids count must equal evidence_count")
        if not isfinite(self.average_reward) or not isfinite(self.total_reward):
            raise ValueError("reward values must be finite")
        if not self.rationale.strip():
            raise ValueError("rationale must not be empty")


@dataclass(frozen=True, slots=True)
class LearningConfig:
    """Conservative thresholds for evidence-backed learning."""

    minimum_evidence: int = 3
    minimum_occurrence_rate: float = 0.50
    reward_clip: float = 3.0
    minimum_negative_reward: float = -0.10

    def __post_init__(self) -> None:
        if self.minimum_evidence < 1:
            raise ValueError("minimum_evidence must be at least 1")
        if not 0 <= self.minimum_occurrence_rate <= 1:
            raise ValueError("minimum_occurrence_rate must be between 0 and 1")
        if self.reward_clip <= 0:
            raise ValueError("reward_clip must be positive")
        if not isfinite(self.minimum_negative_reward):
            raise ValueError("minimum_negative_reward must be finite")


@dataclass(frozen=True, slots=True)
class LearningReport:
    """Immutable Phase-18 learning evidence."""

    experiences: tuple[LearningExperience, ...]
    analyzed_trade_count: int
    rewarded_trade_count: int

    @property
    def experience_count(self) -> int:
        return len(self.experiences)
