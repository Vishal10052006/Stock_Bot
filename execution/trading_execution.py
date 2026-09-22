"""Risk-approved execution boundary.

This module remains broker-free. New execution paths consume the exact
RiskDecision quantity/notional. A compatibility adapter is retained for the
legacy AB-27 backtest gate until the historical engine is migrated to the
full Risk Engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.risk.contracts import RiskDecision as FullRiskDecision
from trading.risk.contracts import RiskDecisionStatus as FullRiskDecisionStatus
from trading.risk.gate import RiskDecision as LegacyRiskDecision
from trading.risk.gate import RiskDecisionStatus as LegacyRiskDecisionStatus
from trading.strategy.models import StrategyDirection


class ExecutionAuthorizationStatus(str, Enum):
    """Execution authorization outcomes."""

    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Immutable downstream authorization."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    status: ExecutionAuthorizationStatus
    reason: str
    risk_version: str
    approved_quantity: float = 0.0
    approved_notional: float = 0.0
    risk_decision_id: str = "legacy-risk-gate"
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
    risk_decision: FullRiskDecision | LegacyRiskDecision,
) -> ExecutionAuthorization:
    """Authorize a full RiskDecision or adapt the legacy AB-27 gate.

    Full RiskDecision preserves the exact approved quantity/notional.
    Legacy AB-27 authorization is retained only for the historical backtest
    until that engine is migrated to the full Risk Engine.
    """
    if isinstance(risk_decision, FullRiskDecision):
        blocked = risk_decision.status is FullRiskDecisionStatus.REJECTED
        return ExecutionAuthorization(
            timestamp=risk_decision.timestamp,
            symbol=risk_decision.symbol,
            direction=StrategyDirection(risk_decision.direction.value),
            status=(
                ExecutionAuthorizationStatus.BLOCKED
                if blocked
                else ExecutionAuthorizationStatus.AUTHORIZED
            ),
            approved_quantity=0.0 if blocked else risk_decision.approved_quantity,
            approved_notional=0.0 if blocked else risk_decision.approved_notional,
            risk_decision_id=risk_decision.decision_id,
            reason=(
                "Execution blocked because RiskDecision is REJECTED."
                if blocked
                else "RiskDecision authorizes the exact approved exposure."
            ),
            risk_version=risk_decision.risk_policy_version,
            restrictions=risk_decision.restrictions,
        )

    if isinstance(risk_decision, LegacyRiskDecision):
        authorized = risk_decision.status is LegacyRiskDecisionStatus.APPROVED
        return ExecutionAuthorization(
            timestamp=risk_decision.timestamp,
            symbol=risk_decision.symbol,
            direction=risk_decision.strategy_direction,
            status=(
                ExecutionAuthorizationStatus.AUTHORIZED
                if authorized
                else ExecutionAuthorizationStatus.BLOCKED
            ),
            reason=risk_decision.reason,
            risk_version=risk_decision.risk_version,
            risk_decision_id="legacy-risk-gate",
            execution_version="legacy-risk-gate-v1.0",
        )

    raise TypeError(
        "risk_decision must be a full RiskDecision or legacy risk-gate RiskDecision"
    )
