"""Composite execution control for the broker-facing boundary.

Risk authorization and independent safety are separate controls. This module
combines their already-evaluated decisions without contacting a broker,
changing risk sizing, or enabling live execution.
"""

from __future__ import annotations

from execution.safety import SafetyDecision
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
    authorize_risk_decision,
)
from trading.risk.gate import RiskDecision


def authorize_execution(
    risk_decision: RiskDecision,
    *,
    approved_quantity: float | None = None,
    approved_notional: float | None = None,
    risk_decision_id: str = "",
    restrictions: tuple[str, ...] = (),
    safety_decision: SafetyDecision,
) -> ExecutionAuthorization:
    """Authorize only when both Risk and independent Safety allow execution.

    Risk remains the sizing authority. A safety veto cannot enlarge, resize,
    or otherwise modify an approved quantity; it only blocks the downstream
    authorization.
    """
    if not isinstance(safety_decision, SafetyDecision):
        raise TypeError("safety_decision must be a SafetyDecision")

    authorization = authorize_risk_decision(
        risk_decision,
        approved_quantity=approved_quantity,
        approved_notional=approved_notional,
        risk_decision_id=risk_decision_id,
        restrictions=restrictions,
    )

    if not safety_decision.allowed:
        return ExecutionAuthorization(
            timestamp=authorization.timestamp,
            symbol=authorization.symbol,
            direction=authorization.direction,
            status=ExecutionAuthorizationStatus.BLOCKED,
            reason=f"Independent safety gate blocked execution: {safety_decision.reason}",
            risk_version=authorization.risk_version,
            approved_quantity=0.0,
            approved_notional=0.0,
            risk_decision_id=authorization.risk_decision_id,
            restrictions=authorization.restrictions + (
                f"safety_block:{safety_decision.block.value}",
            ),
            execution_version=authorization.execution_version,
            position_transition=authorization.position_transition,
            approved_projected_quantity=authorization.approved_projected_quantity,
        )

    return authorization


__all__ = ["authorize_execution"]
