"""Shared Risk Engine contracts and stable reason codes.

References:
- TRADING_SPECIFICATION.md
- docs/RISK_ENGINE.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskAction(str, Enum):
    """Final risk action returned to downstream execution layers."""

    APPROVE = "APPROVE"
    RESIZE = "RESIZE"
    REJECT = "REJECT"


class RiskReasonCode(str, Enum):
    """Stable machine-readable reasons for risk decisions."""

    APPROVED = "APPROVED"
    RESIZED = "RESIZED"
    GENERIC_REJECT = "GENERIC_REJECT"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    LIQUIDITY_INSUFFICIENT = "LIQUIDITY_INSUFFICIENT"
    MAX_TRADES_REACHED = "MAX_TRADES_REACHED"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    MAX_DRAWDOWN_LIMIT = "MAX_DRAWDOWN_LIMIT"
    MAX_OPEN_POSITIONS = "MAX_OPEN_POSITIONS"
    DUPLICATE_SYMBOL = "DUPLICATE_SYMBOL"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_STOP = "INVALID_STOP"
    INVALID_TARGET = "INVALID_TARGET"
    INVALID_REWARD_RISK = "INVALID_REWARD_RISK"
    ZERO_POSITION_SIZE = "ZERO_POSITION_SIZE"
    MAX_GROSS_EXPOSURE = "MAX_GROSS_EXPOSURE"
    SYMBOL_EXPOSURE_LIMIT = "SYMBOL_EXPOSURE_LIMIT"
    SECTOR_EXPOSURE_LIMIT = "SECTOR_EXPOSURE_LIMIT"
    CORRELATION_LIMIT = "CORRELATION_LIMIT"
    VOLATILITY_LIMIT = "VOLATILITY_LIMIT"
    INVALID_RISK_STATE = "INVALID_RISK_STATE"
    STALE_MARKET_DATA = "STALE_MARKET_DATA"
    SYSTEM_NOT_READY = "SYSTEM_NOT_READY"


class RiskPositionTransition(str, Enum):
    """Position-state transition presented to Risk before trade evaluation."""

    OPEN = "OPEN"
    INCREASE = "INCREASE"
    REDUCE = "REDUCE"
    FLATTEN = "FLATTEN"
    REVERSE = "REVERSE"


@dataclass(frozen=True, slots=True)
class RiskPositionContext:
    """Immutable signed position context for deterministic Risk evaluation.

    Quantities are signed from the account's perspective:
    positive = long, negative = short, zero = flat.
    """

    transition: RiskPositionTransition
    existing_quantity: float = 0.0
    projected_quantity: float = 0.0

    def __post_init__(self) -> None:
        import math

        if not all(
            math.isfinite(float(value))
            for value in (self.existing_quantity, self.projected_quantity)
        ):
            raise ValueError("position quantities must be finite")

        if self.transition is RiskPositionTransition.OPEN:
            if self.existing_quantity != 0.0:
                raise ValueError("OPEN requires a flat existing position")
            if self.projected_quantity == 0.0:
                raise ValueError("OPEN requires a non-zero projected position")

        elif self.transition is RiskPositionTransition.INCREASE:
            if self.existing_quantity == 0.0:
                raise ValueError("INCREASE requires an existing position")
            if self.projected_quantity == 0.0:
                raise ValueError("INCREASE requires a non-zero projected position")
            if self.existing_quantity * self.projected_quantity <= 0:
                raise ValueError("INCREASE cannot change position direction")
            if abs(self.projected_quantity) <= abs(self.existing_quantity):
                raise ValueError("INCREASE must increase absolute position size")

        elif self.transition is RiskPositionTransition.REDUCE:
            if self.existing_quantity == 0.0 or self.projected_quantity == 0.0:
                raise ValueError("REDUCE requires non-zero existing and projected positions")
            if self.existing_quantity * self.projected_quantity <= 0:
                raise ValueError("REDUCE cannot change position direction")
            if abs(self.projected_quantity) >= abs(self.existing_quantity):
                raise ValueError("REDUCE must decrease absolute position size")

        elif self.transition is RiskPositionTransition.FLATTEN:
            if self.existing_quantity == 0.0 or self.projected_quantity != 0.0:
                raise ValueError("FLATTEN requires an existing position and zero projection")

        elif self.transition is RiskPositionTransition.REVERSE:
            if self.existing_quantity == 0.0 or self.projected_quantity == 0.0:
                raise ValueError("REVERSE requires non-zero existing and projected positions")
            if self.existing_quantity * self.projected_quantity >= 0:
                raise ValueError("REVERSE must change position direction")

    @property
    def opens_position(self) -> bool:
        """Whether this transition creates directional exposure."""
        return self.transition in {
            RiskPositionTransition.OPEN,
            RiskPositionTransition.INCREASE,
            RiskPositionTransition.REVERSE,
        }

    @property
    def creates_position_slot(self) -> bool:
        """Whether this transition increases the number of open symbols."""
        return self.transition is RiskPositionTransition.OPEN

    @property
    def consumes_trade_entry(self) -> bool:
        """Whether this transition counts against the daily entry budget."""
        return self.transition in {
            RiskPositionTransition.OPEN,
            RiskPositionTransition.INCREASE,
            RiskPositionTransition.REVERSE,
        }

    @property
    def releases_position(self) -> bool:
        """Whether this transition reduces or closes existing exposure."""
        return self.transition in {
            RiskPositionTransition.REDUCE,
            RiskPositionTransition.FLATTEN,
        }


@dataclass(frozen=True, slots=True)
class RiskTransitionSizing:
    """Deterministic order quantities implied by a signed transition.

    order_quantity is the broker-order quantity for the transition.
    closing_quantity is exposure being removed.
    opening_quantity is newly created directional exposure.
    """

    order_quantity: float
    closing_quantity: float
    opening_quantity: float

    def __post_init__(self) -> None:
        import math

        values = (
            self.order_quantity,
            self.closing_quantity,
            self.opening_quantity,
        )
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("transition quantities must be finite")
        if any(float(value) < 0.0 for value in values):
            raise ValueError("transition quantities must be non-negative")

    @classmethod
    def from_context(
        cls,
        context: RiskPositionContext,
    ) -> "RiskTransitionSizing":
        existing = context.existing_quantity
        projected = context.projected_quantity
        delta = projected - existing

        if existing == 0.0:
            closing = 0.0
            opening = abs(projected)
        elif projected == 0.0:
            closing = abs(existing)
            opening = 0.0
        elif existing * projected > 0:
            closing = max(0.0, abs(existing) - abs(projected))
            opening = max(0.0, abs(projected) - abs(existing))
        else:
            closing = abs(existing)
            opening = abs(projected)

        return cls(
            order_quantity=abs(delta),
            closing_quantity=closing,
            opening_quantity=opening,
        )


@dataclass(frozen=True, slots=True)
class RiskCheck:
    """One auditable risk-control result."""

    passed: bool
    reason_code: RiskReasonCode
    message: str
