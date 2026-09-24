"""Risk-approved execution boundary.

This module remains broker-free. It converts a deterministic RiskDecision
plus the Risk Engine's approved quantity into an immutable authorization.
The broker/runtime layer consumes that authorization; this module never
places broker orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.risk.contracts import RiskPositionTransition
from trading.strategy.models import StrategyDirection


class ExecutionAuthorizationStatus(str, Enum):
    """Execution authorization outcomes."""

    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Immutable downstream authorization including approved exposure."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    status: ExecutionAuthorizationStatus
    reason: str
    risk_version: str
    approved_quantity: float = 0.0
    approved_notional: float = 0.0
    risk_decision_id: str = ""
    restrictions: tuple[str, ...] = ()
    execution_version: str = "risk-aware-v2.0"
    position_transition: RiskPositionTransition | None = None
    approved_projected_quantity: float | None = None

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("execution timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("execution symbol must not be empty")
        if self.approved_quantity < 0 or self.approved_notional < 0:
            raise ValueError("approved exposure must be non-negative")


def authorize_risk_decision(
    risk_decision: RiskDecision,
    *,
    approved_quantity: float | None = None,
    approved_notional: float | None = None,
    risk_decision_id: str = "",
    restrictions: tuple[str, ...] = (),
) -> ExecutionAuthorization:
    """Authorize only an approved RiskDecision and preserve approved size.

    The Risk Engine owns sizing. Execution receives the exact quantity selected
    by Risk; it must never reconstruct or enlarge that quantity.
    """
    if not isinstance(risk_decision, RiskDecision):
        raise TypeError("risk_decision must be a RiskDecision")
    blocked = risk_decision.status is not RiskDecisionStatus.APPROVED

    if blocked:
        quantity = 0.0
        notional = 0.0
    else:
        if risk_decision.approved_quantity <= 0:
            raise ValueError("approved RiskDecision must carry a positive quantity")
        if approved_quantity is not None and (
            float(approved_quantity) != risk_decision.approved_quantity
        ):
            raise ValueError("execution quantity must exactly equal RiskDecision approved quantity")
        if approved_notional is not None and (
            float(approved_notional) != risk_decision.approved_notional
        ):
            raise ValueError("execution notional must exactly equal RiskDecision approved notional")
        quantity = risk_decision.approved_quantity
        notional = risk_decision.approved_notional

    return ExecutionAuthorization(
        timestamp=risk_decision.timestamp,
        symbol=risk_decision.symbol,
        direction=risk_decision.strategy_direction,
        status=(
            ExecutionAuthorizationStatus.BLOCKED
            if blocked
            else ExecutionAuthorizationStatus.AUTHORIZED
        ),
        reason=(
            "Execution blocked because RiskDecision is not APPROVED."
            if blocked
            else "RiskDecision authorizes the exact Risk Engine approved exposure."
        ),
        risk_version=risk_decision.risk_version,
        approved_quantity=quantity,
        approved_notional=notional,
        risk_decision_id=risk_decision_id,
        restrictions=restrictions,
        position_transition=risk_decision.position_transition,
        approved_projected_quantity=risk_decision.approved_projected_quantity,
    )
