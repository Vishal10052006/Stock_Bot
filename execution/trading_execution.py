"""Risk-approved execution boundary.

This module remains broker-free. Execution authorization carries the exact
approved risk decision, including quantity and notional limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.risk.contracts import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


class ExecutionAuthorizationStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Immutable downstream authorization derived from RiskDecision."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    status: ExecutionAuthorizationStatus
    approved_quantity: float
    approved_notional: float
    risk_decision_id: str
    reason: str
    risk_version: str
    restrictions: tuple[str, ...] = ()
    execution_version: str = "risk-aware-v2.0"

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("execution timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("execution symbol must not be empty")
        if self.approved_quantity < 0 or self.approved_notional < 0:
            raise ValueError("approved exposure must be non-negative")


def authorize_risk_decision(
    risk_decision: RiskDecision,
) -> ExecutionAuthorization:
    """Authorize only non-rejected RiskDecisions."""
    if not isinstance(risk_decision, RiskDecision):
        raise TypeError("risk_decision must be a RiskDecision")

    status = (
        ExecutionAuthorizationStatus.BLOCKED
        if risk_decision.status is RiskDecisionStatus.REJECTED
        else ExecutionAuthorizationStatus.AUTHORIZED
    )

    if status is ExecutionAuthorizationStatus.BLOCKED:
        return ExecutionAuthorization(
            timestamp=risk_decision.timestamp,
            symbol=risk_decision.symbol,
            direction=StrategyDirection(risk_decision.direction.value),
            status=status,
            approved_quantity=0.0,
            approved_notional=0.0,
            risk_decision_id=risk_decision.decision_id,
            reason="Execution blocked because RiskDecision is REJECTED.",
            risk_version=risk_decision.risk_policy_version,
            restrictions=risk_decision.restrictions,
        )

    return ExecutionAuthorization(
        timestamp=risk_decision.timestamp,
        symbol=risk_decision.symbol,
        direction=StrategyDirection(risk_decision.direction.value),
        status=status,
        approved_quantity=risk_decision.approved_quantity,
        approved_notional=risk_decision.approved_notional,
        risk_decision_id=risk_decision.decision_id,
        reason="RiskDecision authorizes the exact approved exposure.",
        risk_version=risk_decision.risk_policy_version,
        restrictions=risk_decision.restrictions,
    )
