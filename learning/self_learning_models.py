"""Controlled self-learning governance contracts for STOCK_BOT.

The module contains immutable, auditable state objects for the learning loop.
It intentionally contains no broker/execution authority and no direct model
mutation.

References:
    STOCK_BOT self-learning master specification.
    Phase 16-20 learning and experiment contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping


def _fingerprint(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 fingerprint for JSON-like payloads."""
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_text(value: str, field_name: str) -> str:
    """Validate a required textual field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value.strip()


def _require_finite(value: float, field_name: str) -> float:
    """Require a finite numeric value."""
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


class LearningState(str, Enum):
    """Lifecycle states for one controlled learning cycle."""

    OBSERVATION = "OBSERVATION"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    CANDIDATE = "CANDIDATE"
    VALIDATING = "VALIDATING"
    OOS = "OOS"
    WALK_FORWARD = "WALK_FORWARD"
    PAPER = "PAPER"
    PROMOTION_REVIEW = "PROMOTION_REVIEW"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    ROLLED_BACK = "ROLLED_BACK"


class LearningDecision(str, Enum):
    """Research decision values; none authorizes execution."""

    KEEP = "KEEP"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"
    REDESIGN = "REDESIGN"


class FailureClass(str, Enum):
    """Canonical failure categories for learning diagnosis."""

    DATA_FAILURE = "DATA_FAILURE"
    FEATURE_FAILURE = "FEATURE_FAILURE"
    LABEL_FAILURE = "LABEL_FAILURE"
    CAUSALITY_FAILURE = "CAUSALITY_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    CALIBRATION_FAILURE = "CALIBRATION_FAILURE"
    REGIME_FAILURE = "REGIME_FAILURE"
    STRATEGY_FAILURE = "STRATEGY_FAILURE"
    RISK_FAILURE = "RISK_FAILURE"
    EXECUTION_FAILURE = "EXECUTION_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class TradeOutcomeContext:
    """Canonical learning context derived from one completed linked trade."""

    trade_id: str
    decision_id: str
    outcome_timestamp: str
    outcome_label: str
    net_pnl: float
    r_multiple: float
    mae: float
    mfe: float
    holding_minutes: float
    costs: float
    slippage: float
    regime: str | None
    volatility_state: str | None
    symbol: str
    sector: str | None
    model_version: str | None
    strategy_version: str | None
    risk_version: str | None
    execution_version: str | None
    feature_schema_version: str | None
    feature_snapshot: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate immutable outcome context."""
        for name in ("trade_id", "decision_id", "outcome_timestamp", "outcome_label", "symbol"):
            _require_text(getattr(self, name), name)

        for name in (
            "net_pnl",
            "r_multiple",
            "mae",
            "mfe",
            "holding_minutes",
            "costs",
            "slippage",
        ):
            _require_finite(getattr(self, name), name)

        if self.holding_minutes < 0:
            raise ValueError("holding_minutes must be non-negative")
        if self.costs < 0 or self.slippage < 0:
            raise ValueError("costs and slippage must be non-negative")
        if self.mae > 0 or self.mfe < 0:
            raise ValueError("MAE must be <= 0 and MFE must be >= 0")

        object.__setattr__(self, "trade_id", self.trade_id.strip())
        object.__setattr__(self, "decision_id", self.decision_id.strip())
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "feature_snapshot", dict(self.feature_snapshot))

    @property
    def fingerprint(self) -> str:
        """Return deterministic identity for this learning context."""
        return _fingerprint(
            {
                "trade_id": self.trade_id,
                "decision_id": self.decision_id,
                "outcome_timestamp": self.outcome_timestamp,
                "outcome_label": self.outcome_label,
                "net_pnl": self.net_pnl,
                "r_multiple": self.r_multiple,
                "mae": self.mae,
                "mfe": self.mfe,
                "holding_minutes": self.holding_minutes,
                "costs": self.costs,
                "slippage": self.slippage,
                "regime": self.regime,
                "volatility_state": self.volatility_state,
                "symbol": self.symbol,
                "sector": self.sector,
                "model_version": self.model_version,
                "strategy_version": self.strategy_version,
                "risk_version": self.risk_version,
                "execution_version": self.execution_version,
                "feature_schema_version": self.feature_schema_version,
                "feature_snapshot": self.feature_snapshot,
            }
        )


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """Immutable dataset lineage descriptor for one learning experiment."""

    dataset_version: str
    creation_timestamp: str
    source: str
    symbols: tuple[str, ...]
    period_start: str
    period_end: str
    row_count: int
    label_distribution: Mapping[str, int]
    feature_schema_version: str
    label_definition_version: str
    source_trade_ids: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject incomplete or internally inconsistent dataset identities."""
        for name in (
            "dataset_version",
            "creation_timestamp",
            "source",
            "period_start",
            "period_end",
            "feature_schema_version",
            "label_definition_version",
        ):
            _require_text(getattr(self, name), name)

        if self.row_count < 0:
            raise ValueError("row_count must be non-negative")
        if not self.symbols:
            raise ValueError("symbols must contain at least one symbol")
        if any(not isinstance(symbol, str) or not symbol.strip() for symbol in self.symbols):
            raise ValueError("symbols must contain non-empty strings")
        if any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in self.label_distribution.values()
        ):
            raise ValueError("label_distribution values must be non-negative integers")
        if sum(self.label_distribution.values()) != self.row_count:
            raise ValueError("label_distribution must sum to row_count")

        object.__setattr__(
            self,
            "dataset_version",
            self.dataset_version.strip(),
        )
        object.__setattr__(
            self,
            "source",
            self.source.strip(),
        )
        object.__setattr__(
            self,
            "symbols",
            tuple(sorted(symbol.strip().upper() for symbol in self.symbols)),
        )
        object.__setattr__(
            self,
            "label_distribution",
            dict(sorted(self.label_distribution.items())),
        )
        object.__setattr__(
            self,
            "source_trade_ids",
            tuple(sorted(set(self.source_trade_ids))),
        )
        object.__setattr__(self, "known_limitations", tuple(self.known_limitations))

    @property
    def fingerprint(self) -> str:
        """Return deterministic dataset metadata identity."""
        return _fingerprint(
            {
                "dataset_version": self.dataset_version,
                "creation_timestamp": self.creation_timestamp,
                "source": self.source,
                "symbols": list(self.symbols),
                "period_start": self.period_start,
                "period_end": self.period_end,
                "row_count": self.row_count,
                "label_distribution": self.label_distribution,
                "feature_schema_version": self.feature_schema_version,
                "label_definition_version": self.label_definition_version,
                "source_trade_ids": list(self.source_trade_ids),
                "known_limitations": list(self.known_limitations),
            }
        )


@dataclass(frozen=True, slots=True)
class ExperimentLineage:
    """Complete lineage required to reproduce one learning experiment."""

    experiment_id: str
    dataset: DatasetVersion
    code_version: str
    feature_version: str
    label_version: str
    model_version: str
    strategy_version: str
    risk_version: str
    execution_version: str
    change: str
    fixed_components: tuple[str, ...]
    parent_experiment_id: str | None = None

    def __post_init__(self) -> None:
        """Validate lineage identity fields."""
        _require_text(self.experiment_id, "experiment_id")
        _require_text(self.code_version, "code_version")
        _require_text(self.feature_version, "feature_version")
        _require_text(self.label_version, "label_version")
        _require_text(self.model_version, "model_version")
        _require_text(self.strategy_version, "strategy_version")
        _require_text(self.risk_version, "risk_version")
        _require_text(self.execution_version, "execution_version")
        _require_text(self.change, "change")
        if not self.fixed_components:
            raise ValueError("fixed_components must not be empty")

    @property
    def fingerprint(self) -> str:
        """Return deterministic lineage identity."""
        return _fingerprint(
            {
                "experiment_id": self.experiment_id,
                "dataset_fingerprint": self.dataset.fingerprint,
                "code_version": self.code_version,
                "feature_version": self.feature_version,
                "label_version": self.label_version,
                "model_version": self.model_version,
                "strategy_version": self.strategy_version,
                "risk_version": self.risk_version,
                "execution_version": self.execution_version,
                "change": self.change,
                "fixed_components": list(self.fixed_components),
                "parent_experiment_id": self.parent_experiment_id,
            }
        )


@dataclass(frozen=True, slots=True)
class ValidationEvidence:
    """Structured evidence consumed by the promotion gate."""

    integrity_passed: bool
    leakage_passed: bool
    oos_passed: bool
    walk_forward_passed: bool
    paper_passed: bool
    predictive_metrics: Mapping[str, float] = field(default_factory=dict)
    trading_metrics: Mapping[str, float] = field(default_factory=dict)
    regime_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    symbol_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    date_metrics: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    effective_sample_size_notes: str = ""
    issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject non-finite metrics from entering governance state."""
        for group in (
            self.predictive_metrics,
            self.trading_metrics,
            *self.regime_metrics.values(),
            *self.symbol_metrics.values(),
            *self.date_metrics.values(),
        ):
            for name, value in group.items():
                _require_finite(float(value), str(name))

        object.__setattr__(self, "predictive_metrics", dict(self.predictive_metrics))
        object.__setattr__(self, "trading_metrics", dict(self.trading_metrics))
        object.__setattr__(
            self,
            "regime_metrics",
            {str(k): dict(v) for k, v in self.regime_metrics.items()},
        )
        object.__setattr__(
            self,
            "symbol_metrics",
            {str(k): dict(v) for k, v in self.symbol_metrics.items()},
        )
        object.__setattr__(
            self,
            "date_metrics",
            {str(k): dict(v) for k, v in self.date_metrics.items()},
        )
        object.__setattr__(self, "issues", tuple(self.issues))

    @property
    def all_required_gates_pass(self) -> bool:
        """Return whether every mandatory validation boundary passed."""
        return all(
            (
                self.integrity_passed,
                self.leakage_passed,
                self.oos_passed,
                self.walk_forward_passed,
                self.paper_passed,
            )
        )

    @property
    def fingerprint(self) -> str:
        """Return deterministic evidence identity."""
        return _fingerprint(
            {
                "integrity_passed": self.integrity_passed,
                "leakage_passed": self.leakage_passed,
                "oos_passed": self.oos_passed,
                "walk_forward_passed": self.walk_forward_passed,
                "paper_passed": self.paper_passed,
                "predictive_metrics": self.predictive_metrics,
                "trading_metrics": self.trading_metrics,
                "regime_metrics": self.regime_metrics,
                "symbol_metrics": self.symbol_metrics,
                "date_metrics": self.date_metrics,
                "effective_sample_size_notes": self.effective_sample_size_notes,
                "issues": list(self.issues),
            }
        )


@dataclass(frozen=True, slots=True)
class PromotionReview:
    """Deterministic, evidence-backed promotion review."""

    candidate_id: str
    candidate_fingerprint: str
    current_model_version: str
    challenger_model_version: str
    validation: ValidationEvidence
    reproducibility_passed: bool
    governance_approved: bool = False
    decision: LearningDecision = LearningDecision.INCONCLUSIVE
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate promotion review identity fields."""
        for name in (
            "candidate_id",
            "candidate_fingerprint",
            "current_model_version",
            "challenger_model_version",
        ):
            _require_text(getattr(self, name), name)
        if self.current_model_version == self.challenger_model_version:
            raise ValueError("current and challenger model versions must differ")

    @property
    def promotable(self) -> bool:
        """Return whether every non-negotiable gate is satisfied."""
        return (
            self.validation.all_required_gates_pass
            and self.reproducibility_passed
            and self.governance_approved
            and self.decision is LearningDecision.KEEP
        )

    @property
    def fingerprint(self) -> str:
        """Return deterministic promotion-review identity."""
        return _fingerprint(
            {
                "candidate_id": self.candidate_id,
                "candidate_fingerprint": self.candidate_fingerprint,
                "current_model_version": self.current_model_version,
                "challenger_model_version": self.challenger_model_version,
                "validation": self.validation.fingerprint,
                "reproducibility_passed": self.reproducibility_passed,
                "governance_approved": self.governance_approved,
                "decision": self.decision.value,
                "reasons": list(self.reasons),
            }
        )


@dataclass(frozen=True, slots=True)
class ChampionRecord:
    """Immutable champion/challenger history entry."""

    model_version: str
    status: str
    activated_at: str
    experiment_id: str
    promotion_review_fingerprint: str
    parent_model_version: str | None = None
    rollback_of: str | None = None

    def __post_init__(self) -> None:
        """Validate champion history identity."""
        for name in (
            "model_version",
            "status",
            "activated_at",
            "experiment_id",
            "promotion_review_fingerprint",
        ):
            _require_text(getattr(self, name), name)
        if len(self.promotion_review_fingerprint) != 64:
            raise ValueError("promotion_review_fingerprint must be SHA-256")

    @property
    def fingerprint(self) -> str:
        """Return deterministic champion-history identity."""
        return _fingerprint(
            {
                "model_version": self.model_version,
                "status": self.status,
                "activated_at": self.activated_at,
                "experiment_id": self.experiment_id,
                "promotion_review_fingerprint": self.promotion_review_fingerprint,
                "parent_model_version": self.parent_model_version,
                "rollback_of": self.rollback_of,
            }
        )


@dataclass(frozen=True, slots=True)
class LearningCycle:
    """One immutable end-to-end self-learning cycle record."""

    cycle_id: str
    state: LearningState
    experience_fingerprints: tuple[str, ...]
    learning_evidence_fingerprints: tuple[str, ...]
    experiment_id: str | None
    candidate_id: str | None
    promotion_review_fingerprint: str | None
    decision: LearningDecision
    failure_class: FailureClass | None = None
    lesson: str = ""
    next_experiment: str = ""

    def __post_init__(self) -> None:
        """Validate cycle identity and immutable collection fields."""
        _require_text(self.cycle_id, "cycle_id")
        if any(len(value) != 64 for value in self.experience_fingerprints):
            raise ValueError("experience_fingerprints must contain SHA-256 values")
        if any(len(value) != 64 for value in self.learning_evidence_fingerprints):
            raise ValueError("learning_evidence_fingerprints must contain SHA-256 values")
        if self.promotion_review_fingerprint is not None and len(
            self.promotion_review_fingerprint
        ) != 64:
            raise ValueError("promotion_review_fingerprint must be SHA-256")

        object.__setattr__(
            self,
            "experience_fingerprints",
            tuple(self.experience_fingerprints),
        )
        object.__setattr__(
            self,
            "learning_evidence_fingerprints",
            tuple(self.learning_evidence_fingerprints),
        )

    @property
    def fingerprint(self) -> str:
        """Return deterministic cycle identity."""
        return _fingerprint(
            {
                "cycle_id": self.cycle_id,
                "state": self.state.value,
                "experience_fingerprints": list(self.experience_fingerprints),
                "learning_evidence_fingerprints": list(
                    self.learning_evidence_fingerprints
                ),
                "experiment_id": self.experiment_id,
                "candidate_id": self.candidate_id,
                "promotion_review_fingerprint": self.promotion_review_fingerprint,
                "decision": self.decision.value,
                "failure_class": (
                    None
                    if self.failure_class is None
                    else self.failure_class.value
                ),
                "lesson": self.lesson,
                "next_experiment": self.next_experiment,
            }
        )


__all__ = [
    "ChampionRecord",
    "DatasetVersion",
    "ExperimentLineage",
    "FailureClass",
    "LearningCycle",
    "LearningDecision",
    "LearningState",
    "PromotionReview",
    "TradeOutcomeContext",
    "ValidationEvidence",
]
