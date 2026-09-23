"""Contracts for the STOCK_BOT quantitative Strategy Engine.

The Strategy layer decides whether a validated opportunity exists. It does
not size positions, authorize execution, or call a broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import pandas as pd


class StrategyDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


class NoTradeReason(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    STALE_PREDICTION = "STALE_PREDICTION"
    PREDICTION_EDGE_TOO_WEAK = "PREDICTION_EDGE_TOO_WEAK"
    NO_EDGE = "NO_EDGE"
    REGIME_NOT_ELIGIBLE = "REGIME_NOT_ELIGIBLE"
    REGIME_CONFIDENCE_TOO_LOW = "REGIME_CONFIDENCE_TOO_LOW"
    STRATEGY_CONDITION_FAILED = "STRATEGY_CONDITION_FAILED"
    EXPECTED_VALUE_BELOW_THRESHOLD = "EXPECTED_VALUE_BELOW_THRESHOLD"
    COST_TOO_HIGH = "COST_TOO_HIGH"
    LIQUIDITY_INSUFFICIENT = "LIQUIDITY_INSUFFICIENT"
    SIGNAL_CONFLICT = "SIGNAL_CONFLICT"
    CANDIDATE_INVALID = "CANDIDATE_INVALID"


@dataclass(frozen=True, slots=True)
class BaselineStrategyConfig:
    minimum_rvol: float = 1.0
    minimum_regime_probability: float = 0.50
    strategy_version: str = "v1.0"

    def __post_init__(self) -> None:
        if self.minimum_rvol <= 0:
            raise ValueError("minimum_rvol must be positive")
        if not 0.0 <= self.minimum_regime_probability <= 1.0:
            raise ValueError("minimum_regime_probability must be between 0 and 1")
        if not self.strategy_version.strip():
            raise ValueError("strategy_version must not be empty")


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    strategy_id: str = "baseline_trend_v1"
    strategy_version: str = "STRAT-v1.0"
    baseline: BaselineStrategyConfig = field(default_factory=BaselineStrategyConfig)
    prediction_min_probability: float = 0.0
    prediction_min_margin: float = 0.0
    prediction_max_age_seconds: int = 300
    expected_value_threshold: float = 0.0
    max_cost_fraction: float = 1.0
    allowed_regimes: tuple[str, ...] = ("TREND_UP", "TREND_DOWN")
    require_prediction_direction_alignment: bool = False
    require_analysis_alignment: bool = False
    require_liquidity_when_present: bool = True
    cost_model_version: str = "cost-v1.0"
    candidate_policy_version: str = "structure_atr_v1.0"

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id must not be empty")
        if not self.strategy_version.strip():
            raise ValueError("strategy_version must not be empty")
        if not 0.0 <= self.prediction_min_probability <= 1.0:
            raise ValueError("prediction_min_probability must be in [0, 1]")
        if self.prediction_min_margin < 0:
            raise ValueError("prediction_min_margin must be non-negative")
        if self.prediction_max_age_seconds <= 0:
            raise ValueError("prediction_max_age_seconds must be positive")
        if self.max_cost_fraction < 0:
            raise ValueError("max_cost_fraction must be non-negative")
        if not self.allowed_regimes:
            raise ValueError("allowed_regimes must not be empty")
        if not self.cost_model_version.strip():
            raise ValueError("cost_model_version must not be empty")
        if not self.candidate_policy_version.strip():
            raise ValueError("candidate_policy_version must not be empty")


@dataclass(frozen=True, slots=True)
class StrategyDecision:
    """Auditable strategy decision including exact decision-time features."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    strategy_version: str
    rationale: str
    primary_reason: NoTradeReason | None = None
    secondary_reasons: tuple[NoTradeReason, ...] = ()
    prediction_class: str | None = None
    prediction_probability: float | None = None
    prediction_margin: float | None = None
    regime: str | None = None
    regime_probability: float | None = None
    entry_reference: float | None = None
    stop_reference: float | None = None
    target_reference: float | None = None
    expected_reward: float | None = None
    expected_loss: float | None = None
    expected_value: float | None = None
    estimated_cost: float | None = None
    slippage_assumption_bps: float | None = None
    research_version: str | None = None
    analysis_version: str | None = None
    market_version: str | None = None
    prediction_model_version: str | None = None
    feature_version: str | None = None
    cost_model_version: str | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    features: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("strategy timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("strategy symbol must not be empty")
        if not self.strategy_version.strip():
            raise ValueError("strategy_version must not be empty")
        if not self.rationale.strip():
            raise ValueError("rationale must not be empty")
        if self.direction is StrategyDirection.NO_TRADE and self.primary_reason is None:
            object.__setattr__(self, "primary_reason", NoTradeReason.STRATEGY_CONDITION_FAILED)
        elif self.direction is not StrategyDirection.NO_TRADE and self.primary_reason is not None:
            raise ValueError("TRADE decisions must not carry a NO_TRADE primary_reason")
        if self.prediction_probability is not None and not 0.0 <= self.prediction_probability <= 1.0:
            raise ValueError("prediction_probability must be in [0, 1]")
        if self.regime_probability is not None and not 0.0 <= self.regime_probability <= 1.0:
            raise ValueError("regime_probability must be in [0, 1]")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "secondary_reasons", tuple(self.secondary_reasons))
        object.__setattr__(self, "provenance", dict(self.provenance))
        object.__setattr__(self, "features", dict(self.features))


@dataclass(frozen=True, slots=True)
class StrategyInput:
    timestamp: pd.Timestamp
    symbol: str
    decision_features: Mapping[str, Any]
    prediction: Any | None = None
    market_context: Any | None = None
    analysis_context: Any | None = None
    research_context: Any | None = None
    regime: str | None = None
    regime_probability: float | None = None
    cost_estimate: float | None = None
    cost_fraction: float | None = None
    slippage_bps: float | None = None
    liquidity_available: bool | None = None
    versions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("strategy input timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("strategy input symbol must not be empty")
        if not isinstance(self.decision_features, Mapping):
            raise TypeError("decision_features must be a mapping")
        if self.regime_probability is not None and not 0.0 <= self.regime_probability <= 1.0:
            raise ValueError("regime_probability must be in [0, 1]")
        if self.cost_fraction is not None and self.cost_fraction < 0:
            raise ValueError("cost_fraction must be non-negative")
        if self.slippage_bps is not None and self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "decision_features", dict(self.decision_features))
        object.__setattr__(self, "versions", dict(self.versions))
