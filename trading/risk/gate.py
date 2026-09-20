"""AB-27 pre-trade risk gate.

This module establishes a deterministic, broker-free interface from
StrategyDecision to a risk decision. It does not size positions, place
orders, or connect to execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.strategy.models import StrategyDecision, StrategyDirection


class RiskDecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Auditable risk-gate result."""

    timestamp: pd.Timestamp
    symbol: str
    status: RiskDecisionStatus
    strategy_direction: StrategyDirection
    reason: str
    risk_version: str = "v1.0"

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("risk timestamp must be timezone-aware")
        if not self.symbol:
            raise ValueError("risk symbol must not be empty")
        if not self.reason:
            raise ValueError("risk reason must not be empty")


def evaluate_strategy_risk(
    decision: StrategyDecision,
    *,
    risk_enabled: bool = True,
) -> RiskDecision:
    """Apply the first deterministic risk gate to a strategy decision.

    NO_TRADE is always rejected by the pre-trade gate. LONG/SHORT can pass
    the gate when the global risk gate is enabled. Position sizing, daily
    loss limits, correlation exposure, stop-loss/take-profit construction,
    and broker execution remain downstream responsibilities.
    """
    if not isinstance(decision, StrategyDecision):
        raise TypeError("decision must be a StrategyDecision")

    if decision.direction is StrategyDirection.NO_TRADE:
        status = RiskDecisionStatus.REJECTED
        reason = "Strategy produced NO_TRADE; risk gate blocks execution."
    elif not risk_enabled:
        status = RiskDecisionStatus.REJECTED
        reason = "Global risk gate is disabled."
    else:
        status = RiskDecisionStatus.APPROVED
        reason = "Strategy direction passed the deterministic pre-trade risk gate."

    return RiskDecision(
        timestamp=decision.timestamp,
        symbol=decision.symbol,
        status=status,
        strategy_direction=decision.direction,
        reason=reason,
    )
