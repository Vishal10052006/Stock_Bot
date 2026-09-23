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


@dataclass(frozen=True, slots=True)
class RiskCheck:
    """One auditable risk-control result."""

    passed: bool
    reason_code: RiskReasonCode
    message: str
