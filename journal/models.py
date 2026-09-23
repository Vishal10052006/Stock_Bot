"""AB-45/Phase-16 immutable trade journal contracts.

The journal keeps two linked facts:
1. the decision snapshot that existed at decision time, including features,
   model/regime/version context and the reason for trading or not trading;
2. the eventual completed trade outcome.

The two records share a deterministic trade_id. This preserves the causal
decision context instead of reconstructing it later from an outcome.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from typing import Any, Mapping

from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDecision, StrategyDirection


def _json_value(value: Any) -> Any:
    """Normalize supported values into deterministic JSON-safe primitives."""
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, (str, bytes)):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("journal numeric values must be finite")
        return value
    if hasattr(value, "item"):
        return _json_value(value.item())
    raise TypeError(f"unsupported journal value type: {type(value).__name__}")


def _fingerprint(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        _json_value(payload),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True, slots=True)
class TradeDecisionRecord:
    """Immutable snapshot of one strategy decision."""

    trade_id: str
    timestamp: datetime
    symbol: str
    direction: str
    market_regime: str | None
    features: Mapping[str, Any]
    model_version: str | None
    probability: float | None
    entry: float | None
    stop: float | None
    target: float | None
    position_size: float
    failure_reason: str | None
    strategy_version: str
    risk_version: str | None = None
    execution_version: str | None = None
    provenance: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        timestamp = datetime.fromisoformat(self.timestamp.isoformat())
        if timestamp.tzinfo is None:
            raise ValueError("decision timestamp must be timezone-aware")
        if not self.trade_id.strip():
            raise ValueError("trade_id must not be empty")
        if not self.symbol.strip():
            raise ValueError("decision symbol must not be empty")
        if self.direction not in {"LONG", "SHORT", "NO_TRADE"}:
            raise ValueError("invalid decision direction")
        if not self.strategy_version.strip():
            raise ValueError("strategy_version must not be empty")
        if self.position_size < 0 or not math.isfinite(float(self.position_size)):
            raise ValueError("position_size must be finite and non-negative")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        if self.direction == "NO_TRADE" and not self.failure_reason:
            raise ValueError("NO_TRADE decisions require failure_reason")
        if self.entry is not None and self.entry <= 0:
            raise ValueError("entry must be positive when present")
        if self.stop is not None and self.stop <= 0:
            raise ValueError("stop must be positive when present")
        if self.target is not None and self.target <= 0:
            raise ValueError("target must be positive when present")
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "features", dict(self.features))
        object.__setattr__(self, "provenance", dict(self.provenance or {}))

    @classmethod
    def from_strategy_decision(
        cls,
        decision: StrategyDecision,
        *,
        risk_assessment: Any | None = None,
        authorization: Any | None = None,
        trade_id: str | None = None,
    ) -> "TradeDecisionRecord":
        """Capture the strategy decision plus downstream risk/execution facts."""
        if not isinstance(decision, StrategyDecision):
            raise TypeError("decision must be a StrategyDecision")

        entry = getattr(risk_assessment, "entry_price", None)
        stop = getattr(risk_assessment, "stop_price", None)
        target = getattr(risk_assessment, "target_price", None)
        if entry is None:
            entry = decision.entry_reference
        if stop is None:
            stop = decision.stop_reference
        if target is None:
            target = decision.target_reference

        position_size = getattr(risk_assessment, "position_size", None)
        if position_size is None:
            position_size = getattr(authorization, "approved_quantity", 0.0)

        risk_decision = getattr(risk_assessment, "decision", None)
        risk_version = getattr(risk_decision, "risk_version", None)
        execution_version = getattr(authorization, "execution_version", None)

        failure_reason = None
        if decision.direction is StrategyDirection.NO_TRADE:
            failure_reason = (
                decision.primary_reason.value
                if decision.primary_reason is not None
                else "NO_TRADE"
            )
        elif risk_decision is not None:
            risk_status = getattr(risk_decision, "status", None)
            risk_status = getattr(risk_status, "value", risk_status)
            if risk_status != "APPROVED":
                failure_reason = getattr(risk_decision, "reason", None)

        payload = {
            "timestamp": decision.timestamp,
            "symbol": decision.symbol,
            "direction": decision.direction.value,
            "market_regime": decision.regime,
            "features": decision.features,
            "model_version": decision.prediction_model_version,
            "probability": decision.prediction_probability,
            "entry": entry,
            "stop": stop,
            "target": target,
            "position_size": position_size or 0.0,
            "failure_reason": failure_reason,
            "strategy_version": decision.strategy_version,
            "risk_version": risk_version,
            "execution_version": execution_version,
            "provenance": decision.provenance,
        }
        resolved_id = trade_id or _fingerprint(payload)

        return cls(trade_id=resolved_id, **payload)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["record_type"] = "decision"
        return _json_value(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TradeDecisionRecord":
        required = {
            "trade_id", "timestamp", "symbol", "direction", "market_regime",
            "features", "model_version", "probability", "entry", "stop",
            "target", "position_size", "failure_reason", "strategy_version",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"decision record missing required fields: {sorted(missing)}")
        return cls(
            trade_id=str(data["trade_id"]),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            symbol=str(data["symbol"]),
            direction=str(data["direction"]),
            market_regime=data["market_regime"],
            features=dict(data["features"]),
            model_version=data["model_version"],
            probability=(None if data["probability"] is None else float(data["probability"])),
            entry=(None if data["entry"] is None else float(data["entry"])),
            stop=(None if data["stop"] is None else float(data["stop"])),
            target=(None if data["target"] is None else float(data["target"])),
            position_size=float(data["position_size"]),
            failure_reason=data["failure_reason"],
            strategy_version=str(data["strategy_version"]),
            risk_version=data.get("risk_version"),
            execution_version=data.get("execution_version"),
            provenance=dict(data.get("provenance") or {}),
        )


@dataclass(frozen=True, slots=True)
class TradeJournalRecord:
    """Immutable persisted representation of a completed trade."""

    journal_id: str
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float
    holding_minutes: float
    mae: float
    mfe: float
    trade_id: str = ""

    def __post_init__(self) -> None:
        if self.entry_time.tzinfo is None or self.exit_time.tzinfo is None:
            raise ValueError("trade timestamps must be timezone-aware")
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time must not precede entry_time")
        if not self.symbol.strip():
            raise ValueError("trade symbol must not be empty")
        if self.quantity <= 0:
            raise ValueError("trade quantity must be positive")
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("trade prices must be positive")
        if self.mae > 0 or self.mfe < 0:
            raise ValueError("MAE must be <= 0 and MFE must be >= 0")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        if not self.trade_id:
            object.__setattr__(self, "trade_id", self.journal_id)

    @classmethod
    def from_trade_outcome(
        cls,
        outcome: TradeOutcome,
        *,
        trade_id: str | None = None,
    ) -> "TradeJournalRecord":
        if not isinstance(outcome, TradeOutcome):
            raise TypeError("outcome must be a TradeOutcome")

        payload = {
            "symbol": str(outcome.symbol).upper(),
            "direction": outcome.direction.value,
            "entry_time": outcome.entry_time.isoformat(),
            "exit_time": outcome.exit_time.isoformat(),
            "entry_price": float(outcome.entry_price),
            "exit_price": float(outcome.exit_price),
            "quantity": float(outcome.quantity),
            "gross_pnl": float(outcome.gross_pnl),
            "fees": float(outcome.fees),
            "slippage_cost": float(outcome.slippage_cost),
            "net_pnl": float(outcome.net_pnl),
            "holding_minutes": float(outcome.holding_minutes),
            "mae": float(outcome.mae),
            "mfe": float(outcome.mfe),
            "trade_id": trade_id,
        }
        journal_id = _fingerprint(payload)
        resolved_trade_id = trade_id or journal_id
        return cls(
            journal_id=journal_id,
            trade_id=resolved_trade_id,
            symbol=payload["symbol"],
            direction=payload["direction"],
            entry_time=outcome.entry_time.to_pydatetime(),
            exit_time=outcome.exit_time.to_pydatetime(),
            entry_price=payload["entry_price"],
            exit_price=payload["exit_price"],
            quantity=payload["quantity"],
            gross_pnl=payload["gross_pnl"],
            fees=payload["fees"],
            slippage_cost=payload["slippage_cost"],
            net_pnl=payload["net_pnl"],
            holding_minutes=payload["holding_minutes"],
            mae=payload["mae"],
            mfe=payload["mfe"],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["entry_time"] = self.entry_time.isoformat()
        data["exit_time"] = self.exit_time.isoformat()
        data["record_type"] = "outcome"
        return _json_value(data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TradeJournalRecord":
        required = {
            "journal_id", "symbol", "direction", "entry_time", "exit_time",
            "entry_price", "exit_price", "quantity", "gross_pnl", "fees",
            "slippage_cost", "net_pnl", "holding_minutes", "mae", "mfe",
        }
        missing = required.difference(data)
        if missing:
            raise ValueError(f"journal record missing required fields: {sorted(missing)}")
        return cls(
            journal_id=str(data["journal_id"]),
            trade_id=str(data.get("trade_id") or data["journal_id"]),
            symbol=str(data["symbol"]),
            direction=str(data["direction"]),
            entry_time=datetime.fromisoformat(str(data["entry_time"])),
            exit_time=datetime.fromisoformat(str(data["exit_time"])),
            entry_price=float(data["entry_price"]),
            exit_price=float(data["exit_price"]),
            quantity=float(data["quantity"]),
            gross_pnl=float(data["gross_pnl"]),
            fees=float(data["fees"]),
            slippage_cost=float(data["slippage_cost"]),
            net_pnl=float(data["net_pnl"]),
            holding_minutes=float(data["holding_minutes"]),
            mae=float(data["mae"]),
            mfe=float(data["mfe"]),
        )
