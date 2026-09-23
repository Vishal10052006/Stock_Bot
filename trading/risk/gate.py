"""AB-27 deterministic pre-trade risk decision contract.

References:
- TRADING_SPECIFICATION.md
- docs/RISK_ENGINE.md
- docs/PHASE_11_DIRECT_BUILD.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.strategy.models import StrategyDecision, StrategyDirection

from .contracts import RiskAction, RiskReasonCode


class RiskDecisionStatus(str, Enum):
    """Backward-compatible status vocabulary for existing callers."""

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
    risk_version: str = "RISK-v1.0"
    reason_code: RiskReasonCode | None = None

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("risk timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("risk symbol must not be empty")
        if not self.reason.strip():
            raise ValueError("risk reason must not be empty")
        if not self.risk_version.strip():
            raise ValueError("risk_version must not be empty")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())

        if self.reason_code is None:
            code = (
                RiskReasonCode.APPROVED
                if self.status is RiskDecisionStatus.APPROVED
                else RiskReasonCode.GENERIC_REJECT
            )
            object.__setattr__(self, "reason_code", code)

    @property
    def action(self) -> RiskAction:
        """Return the downstream action from the legacy status."""
        return (
            RiskAction.APPROVE
            if self.status is RiskDecisionStatus.APPROVED
            else RiskAction.REJECT
        )


def evaluate_strategy_risk(
    decision: StrategyDecision,
    *,
    risk_enabled: bool = True,
) -> RiskDecision:
    """Apply the legacy deterministic pre-trade gate."""
    if not isinstance(decision, StrategyDecision):
        raise TypeError("decision must be a StrategyDecision")

    if decision.direction is StrategyDirection.NO_TRADE:
        status = RiskDecisionStatus.REJECTED
        reason = "Strategy produced NO_TRADE; risk gate blocks execution."
        reason_code = RiskReasonCode.GENERIC_REJECT
    elif not risk_enabled:
        status = RiskDecisionStatus.REJECTED
        reason = "Global risk gate is disabled."
        reason_code = RiskReasonCode.SYSTEM_NOT_READY
    else:
        status = RiskDecisionStatus.APPROVED
        reason = "Strategy direction passed the deterministic pre-trade risk gate."
        reason_code = RiskReasonCode.APPROVED

    return RiskDecision(
        timestamp=decision.timestamp,
        symbol=decision.symbol,
        status=status,
        strategy_direction=decision.direction,
        reason=reason,
        reason_code=reason_code,
    )


__all__ = [
    "RiskAction",
    "RiskDecision",
    "RiskDecisionStatus",
    "RiskReasonCode",
    "evaluate_strategy_risk",
]
