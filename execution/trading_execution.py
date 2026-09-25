"""Risk-approved execution boundary.

This module remains broker-free. It converts deterministic Risk output plus
independent safety approval into an immutable authorization.

The authorization is the contract between Risk and Execution. Execution may
validate and transport these values, but it must not recalculate or enlarge
them.

References:
- TRADING_SPECIFICATION.md
- docs/PHASE_11_DIRECT_BUILD.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


class ExecutionAuthorizationStatus(str, Enum):
    """Execution authorization outcomes."""

    AUTHORIZED = "AUTHORIZED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    """Immutable downstream authorization including approved trade constraints."""

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

    # Decision-time economics supplied by Risk.
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None

    # Execution constraints supplied upstream. Execution may enforce them but
    # may never widen or relax them.
    max_slippage_bps: float | None = None
    expires_at: pd.Timestamp | None = None

    execution_version: str = "risk-aware-v2.1"

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("execution timestamp must be timezone-aware")

        if not self.symbol.strip():
            raise ValueError("execution symbol must not be empty")

        if self.approved_quantity < 0 or self.approved_notional < 0:
            raise ValueError("approved exposure must be non-negative")

        for name, value in (
            ("entry_price", self.entry_price),
            ("stop_price", self.stop_price),
            ("target_price", self.target_price),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when provided")

        if self.max_slippage_bps is not None and self.max_slippage_bps < 0:
            raise ValueError("max_slippage_bps must be non-negative")

        expires_at = (
            None
            if self.expires_at is None
            else pd.Timestamp(self.expires_at)
        )
        if expires_at is not None and expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "restrictions", tuple(self.restrictions))
        object.__setattr__(self, "expires_at", expires_at)

        if expires_at is not None and expires_at < timestamp:
            raise ValueError("expires_at must not precede authorization timestamp")


def authorize_risk_decision(
    risk_decision: RiskDecision,
    *,
    approved_quantity: float = 0.0,
    approved_notional: float | None = None,
    risk_decision_id: str = "",
    restrictions: tuple[str, ...] = (),
    entry_price: float | None = None,
    stop_price: float | None = None,
    target_price: float | None = None,
    max_slippage_bps: float | None = None,
    expires_at: pd.Timestamp | None = None,
) -> ExecutionAuthorization:
    """Authorize only an approved RiskDecision and preserve exact Risk output.

    Risk owns sizing and trade economics. Execution receives the exact values
    selected upstream and must never reconstruct, enlarge, or loosen them.
    """
    if not isinstance(risk_decision, RiskDecision):
        raise TypeError("risk_decision must be a RiskDecision")

    if approved_quantity < 0:
        raise ValueError("approved_quantity must be non-negative")

    if approved_notional is not None and approved_notional < 0:
        raise ValueError("approved_notional must be non-negative")

    blocked = risk_decision.status is not RiskDecisionStatus.APPROVED
    quantity = 0.0 if blocked else float(approved_quantity)
    notional = 0.0 if blocked else (
        float(approved_notional)
        if approved_notional is not None
        else 0.0
    )

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
        entry_price=None if blocked else entry_price,
        stop_price=None if blocked else stop_price,
        target_price=None if blocked else target_price,
        max_slippage_bps=None if blocked else max_slippage_bps,
        expires_at=None if blocked else expires_at,
    )
