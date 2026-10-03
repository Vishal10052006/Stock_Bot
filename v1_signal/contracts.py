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

It is deliberately broker-free: the system produces the BUY/SELL/WAIT decision and
trade levels for manual real-money execution; constructing or serializing this
contract cannot place, submit, modify, or cancel a broker order.
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
    authority: str = "MANUAL_REAL_MONEY_REVIEW"
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
        if self.authority != "MANUAL_REAL_MONEY_REVIEW":
            raise ValueError("V1 signal authority must remain MANUAL_REAL_MONEY_REVIEW")
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
        payload["is_expired"] = self.is_expired
        payload["broker_execution"] = False
        payload["authority"] = "MANUAL_REAL_MONEY_REVIEW"

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        payload["fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "V1SignalContract":
        """Rehydrate a canonical signal from an already-published JSON snapshot.

        The snapshot is treated as an untrusted transport representation. The
        contract constructor re-runs all invariants, including timestamps,
        evidence causality, authority, and broker-execution locking.
        """
        if not isinstance(data, Mapping):
            raise TypeError("V1 signal payload must be a mapping")

        def evidence_group(key: str) -> tuple[V1Evidence, ...]:
            raw = data.get(key, ())
            if not isinstance(raw, (list, tuple)):
                raise ValueError(f"{key} must be a sequence")
            return tuple(
                V1Evidence(
                    category=str(item["category"]),
                    source=str(item["source"]),
                    timestamp=pd.Timestamp(item["timestamp"]),
                    status=str(item["status"]),
                    reason=str(item["reason"]),
                    details=dict(item.get("details", {})),
                )
                for item in raw
            )

        return cls(
            signal_id=str(data["signal_id"]),
            timestamp=pd.Timestamp(data["timestamp"]),
            symbol=str(data["symbol"]),
            signal=V1Signal(str(data["signal"])),
            entry=None if data.get("entry") is None else float(data["entry"]),
            stop_loss=None if data.get("stop_loss") is None else float(data["stop_loss"]),
            target=None if data.get("target") is None else float(data["target"]),
            risk_reward=None if data.get("risk_reward") is None else float(data["risk_reward"]),
            confidence=None if data.get("confidence") is None else float(data["confidence"]),
            prediction_evidence=dict(data.get("prediction_evidence", {})),
            valid_until=pd.Timestamp(data["valid_until"]),
            news_research_evidence=evidence_group("news_research_evidence"),
            technical_evidence=evidence_group("technical_evidence"),
            fundamental_evidence=evidence_group("fundamental_evidence"),
            market_sector_evidence=evidence_group("market_sector_evidence"),
            supporting_factors=tuple(data.get("supporting_factors", ())),
            contradicting_factors=tuple(data.get("contradicting_factors", ())),
            risk_conditions=tuple(data.get("risk_conditions", ())),
            provenance={str(k): str(v) for k, v in dict(data.get("provenance", {})).items()},
            authority=str(data.get("authority", "MANUAL_REAL_MONEY_REVIEW")),
            broker_execution=bool(data.get("broker_execution", False)),
        )


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


def _deterministic_signal_id(
    *,
    timestamp: pd.Timestamp,
    symbol: str,
    direction: StrategyDirection,
    strategy_version: str,
    entry: float | None,
    stop: float | None,
    target: float | None,
) -> str:
    """Create a stable ID when adapting a canonical paper decision."""
    material = "|".join(
        (
            timestamp.isoformat(),
            symbol.strip().upper(),
            direction.value,
            strategy_version,
            str(entry),
            str(stop),
            str(target),
        )
    )
    return "V1-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def build_v1_signal_from_decision(
    decision: Any,
    *,
    valid_until: pd.Timestamp,
    research_context: Any | None = None,
    market_context: Any | None = None,
) -> V1SignalContract:
    """Adapt the canonical live-paper Strategy/Risk result into V1.

    This is a presentation adapter only. It reuses the already-authoritative
    Prediction/Strategy/Risk outputs and cannot submit or authorize a broker
    order.
    """
    if decision is None or not hasattr(decision, "prediction") or not hasattr(decision, "strategy"):
        raise TypeError("decision must expose prediction and strategy")

    prediction = decision.prediction
    strategy = decision.strategy
    timestamp = pd.Timestamp(strategy.timestamp)
    if timestamp.tzinfo is None:
        raise ValueError("decision timestamp must be timezone-aware")

    direction = strategy.direction
    signal = (
        V1Signal.BUY
        if direction is StrategyDirection.LONG
        else V1Signal.SELL
        if direction is StrategyDirection.SHORT
        else V1Signal.WAIT
    )

    prediction_evidence = {
        "class": getattr(prediction, "predicted_class", None),
        "probabilities": _prediction_probabilities(prediction),
        "probability": strategy.prediction_probability,
        "margin": strategy.prediction_margin,
        "model_version": getattr(prediction, "model_version", None),
        "feature_version": getattr(prediction, "feature_version", None),
        "calibration_version": getattr(prediction, "calibration_version", None),
    }

    technical = (
        V1Evidence(
            category="technical",
            source="strategy-engine",
            timestamp=timestamp,
            status="SUPPORTING" if direction is not StrategyDirection.NO_TRADE else "NEUTRAL",
            reason=strategy.rationale,
            details={
                "regime": strategy.regime,
                "regime_probability": strategy.regime_probability,
                "features": dict(strategy.features),
            },
        ),
    )

    research = ()
    if research_context is not None:
        research_ts = pd.Timestamp(research_context.as_of)
        if research_ts.tzinfo is None:
            raise ValueError("research context timestamp must be timezone-aware")
        research = (
            V1Evidence(
                category="news_research",
                source="research-runtime",
                timestamp=research_ts,
                status="SUPPORTING" if getattr(research_context, "research_stance", "") not in {"NEGATIVE", "BEARISH"} else "CONTRADICTING",
                reason=f"Research stance={getattr(research_context, 'research_stance', 'UNKNOWN')}",
                details={
                    "research_score": getattr(research_context, "research_score", None),
                    "research_confidence": getattr(research_context, "research_confidence", None),
                    "evidence_count": getattr(research_context, "evidence_count", None),
                    "source_count": getattr(research_context, "source_count", None),
                    "conflict_score": getattr(research_context, "conflict_score", None),
                    "research_version": getattr(research_context, "research_version", None),
                },
            ),
        )

    market = ()
    if market_context is not None:
        market_ts = pd.Timestamp(getattr(market_context, "timestamp", timestamp))
        if market_ts.tzinfo is None:
            raise ValueError("market context timestamp must be timezone-aware")
        market = (
            V1Evidence(
                category="market_sector",
                source="market-bot",
                timestamp=market_ts,
                status="OBSERVED",
                reason="Market context used by the canonical analysis path.",
                details={"context": _safe_mapping(market_context)},
            ),
        )

    supporting = []
    contradicting = []
    if strategy.prediction_class and direction.value in {"LONG", "SHORT"}:
        supporting.append(f"Prediction class {strategy.prediction_class} passed strategy evaluation.")
    if strategy.regime:
        supporting.append(f"Regime={strategy.regime} with probability={strategy.regime_probability}.")
    if strategy.primary_reason is not None:
        contradicting.append(strategy.primary_reason.value)

    risk_conditions = [
        f"Risk status={getattr(decision, 'risk_status', 'UNKNOWN')}.",
    ]
    if getattr(decision, "risk_reason", ""):
        risk_conditions.append(str(decision.risk_reason))

    return V1SignalContract(
        signal_id=_deterministic_signal_id(
            timestamp=timestamp,
            symbol=strategy.symbol,
            direction=direction,
            strategy_version=strategy.strategy_version,
            entry=strategy.entry_reference,
            stop=strategy.stop_reference,
            target=strategy.target_reference,
        ),
        timestamp=timestamp,
        symbol=strategy.symbol,
        signal=signal,
        entry=strategy.entry_reference,
        stop_loss=strategy.stop_reference,
        target=strategy.target_reference,
        risk_reward=_rr(direction, strategy.entry_reference, strategy.stop_reference, strategy.target_reference),
        confidence=strategy.prediction_probability,
        prediction_evidence=prediction_evidence,
        valid_until=valid_until,
        news_research_evidence=research,
        technical_evidence=technical,
        market_sector_evidence=market,
        supporting_factors=tuple(supporting),
        contradicting_factors=tuple(contradicting),
        risk_conditions=tuple(risk_conditions),
        provenance={
            "strategy_version": strategy.strategy_version,
            "prediction_model_version": str(getattr(prediction, "model_version", "")),
            "feature_version": str(getattr(prediction, "feature_version", "")),
            "data_version": str(strategy.provenance.get("data_version", "")),
        },
        authority="MANUAL_REAL_MONEY_REVIEW",
        broker_execution=False,
    )


def _prediction_probabilities(prediction: Any) -> dict[str, float]:
    """Return the real model probabilities without synthesizing a distribution."""
    table = getattr(prediction, "probabilities", None)
    if table is None or not hasattr(table, "iloc") or len(table) != 1:
        raise ValueError("prediction probabilities must contain exactly one row")
    row = table.iloc[0]
    keys = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")
    values = {key: float(row[key]) for key in keys}
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values.values()):
        raise ValueError("prediction probabilities must be finite and in [0, 1]")
    if abs(sum(values.values()) - 1.0) > 1e-6:
        raise ValueError("prediction probabilities must sum to 1")
    return values


def _safe_mapping(value: Any) -> dict[str, Any]:
    """Serialize simple context fields without inventing market semantics."""
    if isinstance(value, Mapping):
        return {str(key): value_item for key, value_item in value.items()}
    result = {}
    for key in ("benchmark", "regime", "regime_probability", "trend", "breadth", "volatility"):
        if hasattr(value, key):
            result[key] = getattr(value, key)
    return result


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
        authority="MANUAL_REAL_MONEY_REVIEW",
        broker_execution=False,
    )


__all__ = ["V1Evidence", "V1Signal", "V1SignalContract", "build_v1_signal", "build_v1_signal_from_decision"]
