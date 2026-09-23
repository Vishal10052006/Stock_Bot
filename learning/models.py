"""AB-47 structured learning models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analysis.error_analysis import PatternType


class LearningPattern(str, Enum):
    """Observable patterns eligible for learning."""

    LOSS = "LOSS"
    WIN = "WIN"
    LARGE_MAE = "LARGE_MAE"
    LOW_MFE = "LOW_MFE"
    COST_DRAG = "COST_DRAG"
    REGIME_LOSS_CLUSTER = PatternType.REGIME_LOSS_CLUSTER.value
    LOW_RVOL_SIDEWAYS_BREAKOUT = PatternType.LOW_RVOL_SIDEWAYS_BREAKOUT.value
    HIGH_CONFIDENCE_FALSE_SIGNAL = PatternType.HIGH_CONFIDENCE_FALSE_SIGNAL.value
    OPENING_WINDOW_LOSS = PatternType.OPENING_WINDOW_LOSS.value
    CONSECUTIVE_LOSS_STREAK = PatternType.CONSECUTIVE_LOSS_STREAK.value


@dataclass(frozen=True, slots=True)
class LearningExperience:
    """One evidence-backed learning experience.

    This is an observation, not a model-change instruction.
    """

    pattern: LearningPattern
    symbol: str | None
    evidence_count: int
    population_count: int
    occurrence_rate: float
    confidence: float
    source_trade_ids: tuple[str, ...]
    conditions: tuple[str, ...] = ()
    average_net_pnl: float = 0.0
    total_net_pnl: float = 0.0
    detail: str = ""

    def __post_init__(self) -> None:
        if self.evidence_count < 1:
            raise ValueError(
                "evidence_count must be at least 1"
            )

        if self.population_count < self.evidence_count:
            raise ValueError(
                "population_count must be >= evidence_count"
            )

        if not 0.0 <= self.occurrence_rate <= 1.0:
            raise ValueError(
                "occurrence_rate must be between 0 and 1"
            )

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0 and 1"
            )

        if len(self.source_trade_ids) != self.evidence_count:
            raise ValueError(
                "source_trade_ids count must equal evidence_count"
            )


@dataclass(frozen=True, slots=True)
class LearningConfig:
    """Deterministic learning-evidence thresholds."""

    minimum_evidence: int = 3
    minimum_occurrence_rate: float = 0.50

    def __post_init__(self) -> None:
        if self.minimum_evidence < 1:
            raise ValueError(
                "minimum_evidence must be at least 1"
            )

        if not 0.0 <= self.minimum_occurrence_rate <= 1.0:
            raise ValueError(
                "minimum_occurrence_rate must be between 0 and 1"
            )


@dataclass(frozen=True, slots=True)
class LearningReport:
    """Immutable result produced by AB-47."""

    experiences: tuple[LearningExperience, ...]

    @property
    def experience_count(self) -> int:
        """Number of accepted learning experiences."""

        return len(self.experiences)
