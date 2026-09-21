"""AB-28 execution safety boundary.

This module accepts only an approved RiskDecision. It does not contact a
broker; it produces an immutable execution authorization/intention object.
The existing worker ExecutionEngine remains separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


class ExecutionAuthorizationStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Final pre-broker authorization contract."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    status: ExecutionAuthorizationStatus
    reason: str
    risk_version: str
    execution_version: str = "v1.0"

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("execution timestamp must be timezone-aware")
        if not self.symbol:
            raise ValueError("execution symbol must not be empty")


def authorize_risk_decision(
    risk_decision: RiskDecision,
) -> ExecutionAuthorization:
    """Allow execution only from an approved RiskDecision."""
    if not isinstance(risk_decision, RiskDecision):
        raise TypeError("risk_decision must be a RiskDecision")

    if risk_decision.status is not RiskDecisionStatus.APPROVED:
        return ExecutionAuthorization(
            timestamp=risk_decision.timestamp,
            symbol=risk_decision.symbol,
            direction=risk_decision.strategy_direction,
            status=ExecutionAuthorizationStatus.BLOCKED,
            reason="Execution blocked because RiskDecision is not APPROVED.",
            risk_version=risk_decision.risk_version,
        )

    return ExecutionAuthorization(
        timestamp=risk_decision.timestamp,
        symbol=risk_decision.symbol,
        direction=risk_decision.strategy_direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="RiskDecision is APPROVED for execution routing.",
        risk_version=risk_decision.risk_version,
    )
