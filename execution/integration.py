"""Risk-to-execution integration helpers.

This module is the narrow composition boundary between the existing Risk Engine
and the broker-neutral Execution Engine. It deliberately does not place orders.

References:
- trading/risk/engine.py
- trading/risk/gate.py
- execution/trading_execution.py
- TRADING_SPECIFICATION.md
"""

from __future__ import annotations

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    authorize_risk_decision,
)
from trading.risk.engine import RiskAssessment
from trading.risk.gate import RiskDecision


def authorize_risk_assessment(
    risk_decision: RiskDecision,
    assessment: RiskAssessment,
    *,
    risk_decision_id: str,
    max_slippage_bps: float | None = None,
    expires_at: pd.Timestamp | None = None,
    restrictions: tuple[str, ...] = (),
) -> ExecutionAuthorization:
    """Convert one RiskAssessment into an immutable execution authorization.

    The helper copies the Risk Engine's approved quantity and decision-time
    entry/stop/target values without recalculating them. A rejected assessment
    remains blocked because RiskDecisionStatus is authoritative.

    This is intentionally a composition helper rather than a second risk
    engine. Execution never computes position sizing here.
    """
    if not isinstance(assessment, RiskAssessment):
        raise TypeError("assessment must be a RiskAssessment")
    if not isinstance(risk_decision, RiskDecision):
        raise TypeError("risk_decision must be a RiskDecision")
    if not risk_decision_id.strip():
        raise ValueError("risk_decision_id must not be empty")

    approved_quantity = (
        float(assessment.position_size)
        if assessment.position_size is not None
        else 0.0
    )

    approved_notional = (
        float(assessment.entry_price) * approved_quantity
        if assessment.entry_price is not None
        and approved_quantity > 0
        else 0.0
    )

    return authorize_risk_decision(
        risk_decision,
        approved_quantity=approved_quantity,
        approved_notional=approved_notional,
        risk_decision_id=risk_decision_id,
        restrictions=restrictions,
        entry_price=assessment.entry_price,
        stop_price=assessment.stop_price,
        target_price=assessment.target_price,
        max_slippage_bps=max_slippage_bps,
        expires_at=expires_at,
    )


__all__ = ["authorize_risk_assessment"]
