"""Decision explanation contracts built from authoritative pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import pandas as pd

@dataclass(frozen=True, slots=True)
class DecisionExplanationItem:
    stage: str
    timestamp: pd.Timestamp
    status: str
    reason: str
    source: str

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None: raise ValueError("explanation timestamp must be timezone-aware")
        if not self.stage.strip() or not self.status.strip() or not self.reason.strip() or not self.source.strip():
            raise ValueError("explanation fields must not be empty")
        object.__setattr__(self, "timestamp", ts)

@dataclass(frozen=True, slots=True)
class DecisionExplanation:
    timestamp: pd.Timestamp
    symbol: str
    outcome: str
    items: tuple[DecisionExplanationItem, ...]
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None: raise ValueError("decision timestamp must be timezone-aware")
        symbol = self.symbol.strip().upper()
        if not symbol: raise ValueError("symbol must not be empty")
        if any(item.timestamp > ts for item in self.items): raise ValueError("future explanation evidence rejected")
        stage_order = {"Market": 10, "Analysis": 20, "Prediction": 30, "Research": 35, "Screen": 40, "Strategy": 50, "Risk": 60, "Safety": 70, "Execution": 80}
        ordered = tuple(sorted(
            self.items,
            key=lambda item: (item.timestamp, stage_order.get(item.stage, 999), item.stage, item.source),
        ))
        object.__setattr__(self, "timestamp", ts)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "items", ordered)

    def as_dict(self) -> dict[str, object]:
        return {"timestamp": self.timestamp.isoformat(), "symbol": self.symbol, "outcome": self.outcome, "authority": self.authority, "items": tuple({"stage": i.stage, "timestamp": i.timestamp.isoformat(), "status": i.status, "reason": i.reason, "source": i.source} for i in self.items)}

def _field(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None: return default
    if isinstance(obj, Mapping): return obj.get(name, default)
    return getattr(obj, name, default)

def _item(stage: str, obj: Any, timestamp: pd.Timestamp, source: str) -> DecisionExplanationItem | None:
    if obj is None:
        return None
    nested = _field(obj, "snapshot", None)
    ts = pd.Timestamp(
        _field(
            obj,
            "timestamp",
            _field(nested, "updated_at", timestamp),
        )
    )
    if stage == "Safety":
        allowed = _field(obj, "allowed", None)
        status = "ALLOWED" if allowed is True else "BLOCKED" if allowed is False else "OBSERVED"
    elif stage == "Execution" and nested is not None:
        status = _enum_value(_field(nested, "status", None)) or "OBSERVED"
    else:
        raw_status = _field(obj, "status", None)
        if raw_status is None:
            raw_status = _field(obj, "direction", "OBSERVED")
        status = _enum_value(raw_status) or "OBSERVED"

    if stage == "Strategy":
        primary = _enum_value(_field(obj, "primary_reason", None))
        secondary = tuple(
            value for value in (
                _enum_value(reason) for reason in _field(obj, "secondary_reasons", ())
            )
            if value
        )
        rationale = _field(obj, "rationale", "")
        if primary:
            reason = primary
            if secondary:
                reason = f"{reason}; secondary={','.join(secondary)}"
        else:
            reason = rationale
    elif stage == "Safety":
        reason = _field(obj, "reason", "")
        block = _enum_value(_field(obj, "block", None))
        if block and block != "NONE" and block not in str(reason).upper():
            reason = f"{block}: {reason}"
    elif stage == "Execution":
        reason = _field(nested, "reason", _field(obj, "reason", _field(obj, "error", "")))
    else:
        reason = _field(
            obj,
            "reason",
            _field(obj, "rationale", _field(nested, "reason", "")),
        )
    # Strategy direction itself is authoritative evidence when no explicit
    # reason/rationale field is present. Keep the evidence item so the audit
    # layer can validate outcome consistency without inventing a cause.
    if not str(reason).strip():
        if stage == "Strategy":
            reason = status
        elif stage == "Safety" and status in {"ALLOWED", "BLOCKED"}:
            reason = status
        elif stage == "Execution" and status != "OBSERVED":
            reason = status
        else:
            return None
    return DecisionExplanationItem(stage, ts, str(status), str(reason), source)

def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value)).split(".")[-1].upper()

def _execution_outcome(execution: Any) -> str | None:
    status = _enum_value(_field(execution, "status", None))
    if status is None:
        return None
    return {
        "BLOCKED": "EXECUTION_BLOCKED",
        "REJECTED": "EXECUTION_REJECTED",
        "REJECTED_LOCAL": "EXECUTION_REJECTED",
        "REJECTED_BROKER": "EXECUTION_REJECTED",
        "FAILED": "EXECUTION_REJECTED",
        "FILLED": "EXECUTION_FILLED",
        "PARTIALLY_FILLED": "EXECUTION_PENDING",
        "SUBMITTED": "EXECUTION_PENDING",
        "ACKNOWLEDGED": "EXECUTION_PENDING",
        "OPEN": "EXECUTION_PENDING",
        "CANCEL_PENDING": "EXECUTION_PENDING",
    }.get(status)
def build_decision_explanation(
    timestamp: pd.Timestamp,
    symbol: str,
    *,
    strategy: Any = None,
    risk: Any = None,
    safety: Any = None,
    execution: Any = None,
    research: Any = None,
    screen: Any = None,
    market: Any = None,
    analysis: Any = None,
    prediction: Any = None,
) -> DecisionExplanation:
    """Compose explanations from existing evidence without inventing causes."""
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is None: raise ValueError("decision timestamp must be timezone-aware")
    items = []
    for stage, obj, source in (
        ("Market", market, "market"),
        ("Analysis", analysis, "analysis"),
        ("Prediction", prediction, "prediction"),
        ("Research", research, "research"),
        ("Screen", screen, "screen_observer"),
        ("Strategy", strategy, "strategy"),
        ("Risk", risk, "risk"),
        ("Safety", safety, "safety"),
        ("Execution", execution, "execution"),
    ):
        item = _item(stage, obj, timestamp, source)
        if item is not None: items.append(item)
    for component in (market, analysis, prediction, research, screen, strategy, risk, safety, execution):
        if component is None:
            continue
        component_ts = _field(
            component,
            "timestamp",
            _field(_field(component, "snapshot", None), "updated_at", None),
        )
        if component_ts is not None and pd.Timestamp(component_ts) > timestamp:
            raise ValueError("future explanation evidence rejected")
        component_symbol = _field(
            component,
            "symbol",
            _field(_field(component, "request", None), "symbol", None),
        )
        if component_symbol is not None and str(component_symbol).strip().upper() != str(symbol).strip().upper():
            raise ValueError("explanation symbol mismatch")
    strategy_direction = _enum_value(_field(strategy, "direction", None))
    risk_status = _enum_value(_field(risk, "status", None))
    safety_allowed = _field(safety, "allowed", None)
    execution_evidence = _field(execution, "snapshot", None) or execution
    execution_outcome = _execution_outcome(execution_evidence)
    if strategy_direction == "NO_TRADE":
        outcome = "NO_TRADE"
    elif safety_allowed is False:
        outcome = "SAFETY_BLOCKED"
    elif risk_status == "REJECTED":
        outcome = "RISK_REJECTED"
    elif execution_outcome is not None:
        outcome = execution_outcome
    elif strategy_direction in {"LONG", "SHORT"}:
        outcome = strategy_direction
    else:
        outcome = "OBSERVATION_ONLY"
    return DecisionExplanation(timestamp, symbol, outcome, tuple(items))

__all__ = ["DecisionExplanationItem", "DecisionExplanation", "build_decision_explanation"]
