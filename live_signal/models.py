"""Immutable Phase 21 live-signal contracts.

References:
- docs/STRATEGY_ENGINE.md
- docs/FINAL_SYSTEM_AUDIT.md
- TRADING_SPECIFICATION.md

The signal layer is deliberately broker-free. It describes the decision
produced by the existing Strategy and Risk authorities; it does not authorize
or execute a broker order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

import pandas as pd

from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDecision, StrategyDirection


class LiveSignalStatus(str, Enum):
    """Final Phase-21 signal state."""

    ACTIONABLE = "ACTIONABLE"
    NO_TRADE = "NO_TRADE"


class SignalNoTradeReason(str, Enum):
    """Phase-21 operational reasons for a non-actionable signal."""

    STALE_DATA = "STALE_DATA"
    INVALID_INPUT = "INVALID_INPUT"
    PIPELINE_ERROR = "PIPELINE_ERROR"
    STRATEGY_REJECTED = "STRATEGY_REJECTED"
    RISK_REJECTED = "RISK_REJECTED"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"


@dataclass(frozen=True, slots=True)
class LiveSignalInput:
    """All decision-time inputs required to construct one live signal."""

    timestamp: pd.Timestamp
    symbol: str
    decision_features: Mapping[str, Any]
    risk_state: Any
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
            raise ValueError("live signal timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("live signal symbol must not be empty")
        if not isinstance(self.decision_features, Mapping):
            raise TypeError("decision_features must be a mapping")
        if self.regime_probability is not None and not 0.0 <= self.regime_probability <= 1.0:
            raise ValueError("regime_probability must be in [0, 1]")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "decision_features", dict(self.decision_features))
        object.__setattr__(self, "versions", dict(self.versions))


@dataclass(frozen=True, slots=True)
class LiveSignal:
    """Immutable, deterministic, auditable Phase-21 output."""

    signal_id: str
    timestamp: pd.Timestamp
    symbol: str
    status: LiveSignalStatus
    direction: StrategyDirection
    strategy: StrategyDecision
    risk: RiskDecision
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    position_size: float | None = None
    rationale: str = ""
    no_trade_reason: SignalNoTradeReason | None = None
    risk_reason: str = ""
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("signal timestamp must be timezone-aware")
        if not self.signal_id.strip():
            raise ValueError("signal_id must not be empty")
        if not self.symbol.strip():
            raise ValueError("signal symbol must not be empty")
        if self.strategy.timestamp != timestamp:
            raise ValueError("strategy timestamp must match signal timestamp")
        if self.strategy.symbol != self.symbol:
            raise ValueError("strategy symbol must match signal symbol")
        if self.risk.timestamp != timestamp:
            raise ValueError("risk timestamp must match signal timestamp")
        if self.risk.symbol != self.symbol:
            raise ValueError("risk symbol must match signal symbol")

        actionable = self.status is LiveSignalStatus.ACTIONABLE
        if actionable:
            if self.direction is StrategyDirection.NO_TRADE:
                raise ValueError("ACTIONABLE signal cannot be NO_TRADE")
            if self.risk.status is not RiskDecisionStatus.APPROVED:
                raise ValueError("ACTIONABLE signal requires approved RiskDecision")
            if self.position_size is None or self.position_size <= 0:
                raise ValueError("ACTIONABLE signal requires positive position_size")
            if self.no_trade_reason is not None:
                raise ValueError("ACTIONABLE signal cannot have no_trade_reason")
        else:
            if self.direction is not StrategyDirection.NO_TRADE:
                if self.risk.status is not RiskDecisionStatus.REJECTED:
                    raise ValueError(
                        "non-actionable directional signal requires rejected RiskDecision"
                    )
            if self.no_trade_reason is None:
                raise ValueError("NO_TRADE signal requires no_trade_reason")
            if self.position_size not in (None, 0.0):
                raise ValueError("NO_TRADE signal cannot carry position_size")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "provenance", dict(self.provenance))

    @property
    def is_actionable(self) -> bool:
        """Return whether the signal is eligible for the downstream paper boundary."""
        return self.status is LiveSignalStatus.ACTIONABLE

    @staticmethod
    def deterministic_id(
        *,
        timestamp: pd.Timestamp,
        symbol: str,
        strategy_version: str,
        prediction_model_version: str | None,
        feature_version: str | None,
        risk_version: str,
    ) -> str:
        """Build a stable identity for one decision-time pipeline state."""
        payload = {
            "timestamp": pd.Timestamp(timestamp).isoformat(),
            "symbol": symbol.strip().upper(),
            "strategy_version": strategy_version,
            "prediction_model_version": prediction_model_version or "",
            "feature_version": feature_version or "",
            "risk_version": risk_version,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly audit representation."""
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "status": self.status.value,
            "direction": self.direction.value,
            "strategy_version": self.strategy.strategy_version,
            "strategy_rationale": self.strategy.rationale,
            "strategy_reason": (
                self.strategy.primary_reason.value
                if self.strategy.primary_reason is not None
                else None
            ),
            "risk_status": self.risk.status.value,
            "risk_reason": self.risk.reason,
            "risk_version": self.risk.risk_version,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "position_size": self.position_size,
            "no_trade_reason": (
                self.no_trade_reason.value if self.no_trade_reason is not None else None
            ),
            "provenance": dict(self.provenance),
        }
