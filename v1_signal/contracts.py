"""Canonical Version-1 human-review signal contract.

References:
- VERSION-1-TARGET.txt
- VERSION-01-ROADMAP-DEFINITION-OF-DONE.txt
- live_signal/models.py
- trading/strategy/models.py
- trading/risk/gate.py

The contract is the single presentation boundary for V1. It contains the
authoritative BUY/SELL/WAIT decision, trade levels, evidence, risk conditions,
and provenance needed by the dashboard and human reviewer.

It is deliberately broker-free: constructing or serializing this contract
cannot place, submit, modify, or cancel a broker order.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping

import pandas as pd

from live_signal.models import LiveSignal, LiveSignalStatus
from trading.strategy.models import StrategyDirection


class V1Signal(str, Enum):
    """Human-review action vocabulary required by Version 1."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class V1Evidence:
    """One piece of decision-time evidence with explicit provenance."""

    category: str
    source: str
    timestamp: pd.Timestamp
    status: str
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("V1 evidence timestamp must be timezone-aware")
        if not self.category.strip():
            raise ValueError("V1 evidence category must not be empty")
        if not self.source.strip():
            raise ValueError("V1 evidence source must not be empty")
        if not self.status.strip():
            raise ValueError("V1 evidence status must not be empty")
        if not self.reason.strip():
            raise ValueError("V1 evidence reason must not be empty")
        if not isinstance(self.details, Mapping):
            raise TypeError("V1 evidence details must be a mapping")
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "details", dict(self.details))


@dataclass(frozen=True, slots=True)
class V1SignalContract:
    """Immutable canonical signal presented to the human reviewer."""

    signal_id: str
    timestamp: pd.Timestamp
    symbol: str
    signal: V1Signal
    entry: float | None
    stop_loss: float | None
    target: float | None
    risk_reward: float | None
    confidence: float | None
    prediction_evidence: Mapping[str, Any]
    valid_until: pd.Timestamp
    news_research_evidence: tuple[V1Evidence, ...] = ()
    technical_evidence: tuple[V1Evidence, ...] = ()
    fundamental_evidence: tuple[V1Evidence, ...] = ()
    market_sector_evidence: tuple[V1Evidence, ...] = ()
    supporting_factors: tuple[str, ...] = ()
    contradicting_factors: tuple[str, ...] = ()
    risk_conditions: tuple[str, ...] = ()
    provenance: Mapping[str, str] = field(default_factory=dict)
    authority: str = "HUMAN_REVIEW_ONLY"
    broker_execution: bool = False

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        valid_until = pd.Timestamp(self.valid_until)
        if ts.tzinfo is None or valid_until.tzinfo is None:
            raise ValueError("V1 timestamps must be timezone-aware")
        if valid_until < ts:
            raise ValueError("valid_until must not precede signal timestamp")
        if not self.signal_id.strip():
            raise ValueError("signal_id must not be empty")
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if self.entry is not None and not _finite(self.entry, "entry"):
            raise ValueError("entry must be finite")
        if self.stop_loss is not None and not _finite(self.stop_loss, "stop_loss"):
            raise ValueError("stop_loss must be finite")
        if self.target is not None and not _finite(self.target, "target"):
            raise ValueError("target must be finite")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.signal is V1Signal.WAIT:
            # WAIT is allowed to carry contextual levels, but never a broker
            # execution authority or a fabricated risk/reward ratio.
            if self.broker_execution:
                raise ValueError("WAIT signal cannot enable broker execution")
        if self.authority != "HUMAN_REVIEW_ONLY":
            raise ValueError("V1 signal authority must remain HUMAN_REVIEW_ONLY")
        if self.broker_execution:
            raise ValueError("V1 contract must never authorize broker execution")
        if not isinstance(self.prediction_evidence, Mapping):
            raise TypeError("prediction_evidence must be a mapping")

        evidence_groups = (
            self.news_research_evidence,
            self.technical_evidence,
            self.fundamental_evidence,
            self.market_sector_evidence,
        )
        for group in evidence_groups:
            for item in group:
                if item.timestamp > ts:
                    raise ValueError("future V1 evidence rejected")

        if self.risk_reward is not None and self.risk_reward < 0:
            raise ValueError("risk_reward must be non-negative")

        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "valid_until", valid_until)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "prediction_evidence", dict(self.prediction_evidence))
        object.__setattr__(self, "provenance", dict(self.provenance))
        object.__setattr__(self, "supporting_factors", tuple(self.supporting_factors))
        object.__setattr__(self, "contradicting_factors", tuple(self.contradicting_factors))
        object.__setattr__(self, "risk_conditions", tuple(self.risk_conditions))

    @property
    def is_expired(self) -> bool:
        """Return whether the contract has passed its explicit validity boundary."""
        return pd.Timestamp.now(tz="UTC") > self.valid_until

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dashboard/API representation."""
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        payload["valid_until"] = self.valid_until.isoformat()
        payload["signal"] = self.signal.value

        for key in (
            "news_research_evidence",
            "technical_evidence",
            "fundamental_evidence",
            "market_sector_evidence",
        ):
            payload[key] = [
                {
                    **item,
                    "timestamp": item["timestamp"].isoformat(),
                }
                for item in payload[key]
            ]

        payload["risk_reward"] = self.risk_reward
        payload["broker_execution"] = False
        payload["authority"] = "HUMAN_REVIEW_ONLY"

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload


def _finite(value: float, field_name: str) -> bool:
    """Return True only for finite numeric values."""
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return True


def _rr(direction: StrategyDirection, entry: float | None, stop: float | None, target: float | None) -> float | None:
    """Calculate reward/risk from authoritative trade references."""
    if entry is None or stop is None or target is None:
        return None
    risk = abs(float(entry) - float(stop))
    reward = abs(float(target) - float(entry))
    if risk == 0:
        return None
    return reward / risk


def _prediction_evidence(signal: LiveSignal) -> dict[str, Any]:
    """Expose existing prediction fields without creating new predictions."""
    strategy = signal.strategy
    return {
        "class": strategy.prediction_class,
        "probability": strategy.prediction_probability,
        "margin": strategy.prediction_margin,
        "model_version": strategy.prediction_model_version,
        "feature_version": strategy.feature_version,
    }


def build_v1_signal(
    live_signal: LiveSignal,
    *,
    valid_until: pd.Timestamp,
    news_research_evidence: tuple[V1Evidence, ...] = (),
    technical_evidence: tuple[V1Evidence, ...] = (),
    fundamental_evidence: tuple[V1Evidence, ...] = (),
    market_sector_evidence: tuple[V1Evidence, ...] = (),
    supporting_factors: tuple[str, ...] = (),
    contradicting_factors: tuple[str, ...] = (),
    risk_conditions: tuple[str, ...] = (),
) -> V1SignalContract:
    """Adapt the existing LiveSignal into the canonical V1 review contract."""
    if not isinstance(live_signal, LiveSignal):
        raise TypeError("live_signal must be a LiveSignal")

    if live_signal.status is LiveSignalStatus.ACTIONABLE:
        signal = (
            V1Signal.BUY
            if live_signal.direction is StrategyDirection.LONG
            else V1Signal.SELL
        )
    else:
        signal = V1Signal.WAIT

    entry = live_signal.entry_price
    stop = live_signal.stop_price
    target = live_signal.target_price

    return V1SignalContract(
        signal_id=live_signal.signal_id,
        timestamp=live_signal.timestamp,
        symbol=live_signal.symbol,
        signal=signal,
        entry=entry,
        stop_loss=stop,
        target=target,
        risk_reward=_rr(live_signal.direction, entry, stop, target),
        confidence=live_signal.strategy.prediction_probability,
        prediction_evidence=_prediction_evidence(live_signal),
        valid_until=valid_until,
        news_research_evidence=news_research_evidence,
        technical_evidence=technical_evidence,
        fundamental_evidence=fundamental_evidence,
        market_sector_evidence=market_sector_evidence,
        supporting_factors=supporting_factors,
        contradicting_factors=contradicting_factors,
        risk_conditions=tuple(
            list(risk_conditions)
            + ([live_signal.risk_reason] if live_signal.risk_reason else [])
        ),
        provenance=live_signal.provenance,
        authority="HUMAN_REVIEW_ONLY",
        broker_execution=False,
    )


__all__ = ["V1Evidence", "V1Signal", "V1SignalContract", "build_v1_signal"]
