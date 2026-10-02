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
        ordered = tuple(sorted(self.items, key=lambda item: (item.timestamp, item.stage, item.source)))
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
    if obj is None: return None
    ts = pd.Timestamp(_field(obj, "timestamp", timestamp))
    status = _field(obj, "status", _field(obj, "direction", "OBSERVED"))
    reason = _field(obj, "reason", _field(obj, "rationale", ""))
    if not str(reason).strip(): return None
    return DecisionExplanationItem(stage, ts, str(status), str(reason), source)

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
        component_ts = _field(component, "timestamp", None)
        if component_ts is not None and pd.Timestamp(component_ts) > timestamp:
            raise ValueError("future explanation evidence rejected")
        component_symbol = _field(component, "symbol", None)
        if component_symbol is not None and str(component_symbol).strip().upper() != str(symbol).strip().upper():
            raise ValueError("explanation symbol mismatch")
    strategy_direction = _field(strategy, "direction", None)
    risk_status = _field(risk, "status", None)
    safety_allowed = _field(safety, "allowed", None)
    execution_status = _field(execution, "status", None)
    if strategy_direction is not None and str(strategy_direction).split(".")[-1] == "NO_TRADE": outcome = "NO_TRADE"
    elif execution_status is not None and str(execution_status).split(".")[-1] == "BLOCKED": outcome = "EXECUTION_BLOCKED"
    elif risk_status is not None and str(risk_status).split(".")[-1] == "REJECTED": outcome = "RISK_REJECTED"
    elif safety_allowed is False: outcome = "SAFETY_BLOCKED"
    elif strategy_direction is not None: outcome = str(strategy_direction).split(".")[-1]
    else: outcome = "OBSERVATION_ONLY"
    return DecisionExplanation(timestamp, symbol, outcome, tuple(items))

__all__ = ["DecisionExplanationItem", "DecisionExplanation", "build_decision_explanation"]
