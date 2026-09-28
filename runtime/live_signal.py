"""Phase-21 live signal engine.

The engine converts one already-constructed causal StrategyInput into an
auditable live signal observation. It owns no Risk, Safety, Paper, or Broker
authority. Signals are informational until downstream Risk authorization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from trading.strategy.engine import StrategyEngine, StrategyTrace
from trading.strategy.models import StrategyConfig, StrategyDecision, StrategyDirection


@dataclass(frozen=True, slots=True)
class LiveSignal:
    """Immutable live signal observation at one decision timestamp."""

    signal_id: str
    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    strategy_version: str
    rationale: str
    primary_reason: str | None
    prediction_probability: float | None
    prediction_model_version: str | None
    regime: str | None
    regime_probability: float | None
    feature_version: str | None
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_decision(
        cls,
        decision: StrategyDecision,
        *,
        signal_id: str,
    ) -> "LiveSignal":
        reason = decision.primary_reason.value if decision.primary_reason else None
        return cls(
            signal_id=signal_id,
            timestamp=pd.Timestamp(decision.timestamp),
            symbol=decision.symbol,
            direction=decision.direction,
            strategy_version=decision.strategy_version,
            rationale=decision.rationale,
            primary_reason=reason,
            prediction_probability=decision.prediction_probability,
            prediction_model_version=decision.prediction_model_version,
            regime=decision.regime,
            regime_probability=decision.regime_probability,
            feature_version=decision.feature_version,
            provenance=dict(decision.provenance),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "direction": self.direction.value,
            "strategy_version": self.strategy_version,
            "rationale": self.rationale,
            "primary_reason": self.primary_reason,
            "prediction_probability": self.prediction_probability,
            "prediction_model_version": self.prediction_model_version,
            "regime": self.regime,
            "regime_probability": self.regime_probability,
            "feature_version": self.feature_version,
            "provenance": dict(self.provenance),
            "live_broker_order_submission": False,
        }


@dataclass(frozen=True, slots=True)
class LiveSignalResult:
    signal: LiveSignal
    trace: StrategyTrace

    def evidence(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal.signal_id,
            "symbol": self.signal.symbol,
            "timestamp": self.signal.timestamp.isoformat(),
            "direction": self.signal.direction.value,
            "strategy_version": self.signal.strategy_version,
            "live_broker_order_submission": False,
        }


class LiveSignalEngine:
    """Causal signal adapter around the authoritative StrategyEngine."""

    def __init__(
        self,
        *,
        strategy_engine: StrategyEngine | None = None,
        strategy_config: StrategyConfig | None = None,
        max_input_age_seconds: int = 30,
    ) -> None:
        if max_input_age_seconds <= 0:
            raise ValueError("max_input_age_seconds must be positive")
        self.strategy_engine = strategy_engine or StrategyEngine(strategy_config)
        self.max_input_age_seconds = max_input_age_seconds
        self._last_timestamp: dict[str, pd.Timestamp] = {}

    def evaluate(
        self,
        strategy_input: Any,
        *,
        observed_at: datetime | pd.Timestamp | None = None,
    ) -> LiveSignalResult:
        """Evaluate one causal StrategyInput and emit a signal observation."""
        from trading.strategy.models import StrategyInput

        if not isinstance(strategy_input, StrategyInput):
            raise TypeError("strategy_input must be a StrategyInput")

        timestamp = pd.Timestamp(strategy_input.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("signal timestamp must be timezone-aware")

        now = pd.Timestamp(observed_at or datetime.now(timezone.utc))
        if now.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        now = now.tz_convert("UTC")
        timestamp = timestamp.tz_convert("UTC")

        if timestamp > now:
            raise ValueError("live signal timestamp cannot be in the future")
        age = (now - timestamp).total_seconds()
        if age > self.max_input_age_seconds:
            raise ValueError(
                f"signal input is stale by {age:.3f}s; "
                f"maximum is {self.max_input_age_seconds}s"
            )

        previous = self._last_timestamp.get(strategy_input.symbol)
        if previous is not None and timestamp <= previous:
            raise ValueError("live signal timestamps must be strictly increasing per symbol")

        decision, trace = self.strategy_engine.decide(strategy_input)
        signal_id = (
            f"{timestamp.isoformat()}:{decision.symbol}:"
            f"{decision.strategy_version}:{decision.direction.value}"
        )
        signal = LiveSignal.from_decision(decision, signal_id=signal_id)
        self._last_timestamp[decision.symbol] = timestamp
        return LiveSignalResult(signal=signal, trace=trace)

    def reset(self) -> None:
        self._last_timestamp.clear()
