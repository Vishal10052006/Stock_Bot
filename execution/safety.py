"""Independent execution safety and kill-switch boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SafetyBlock(str, Enum):
    NONE = "NONE"
    KILL_SWITCH = "KILL_SWITCH"
    STALE_DATA = "STALE_DATA"
    DATA_QUALITY = "DATA_QUALITY"
    SESSION_CLOSED = "SESSION_CLOSED"
    LIVE_LOCKED = "LIVE_LOCKED"


@dataclass(frozen=True, slots=True)
class SafetyState:
    """Point-in-time safety state independent of model decisions."""

    kill_switch_active: bool = False
    stale_data: bool = False
    data_quality_ok: bool = True
    session_open: bool = True
    live_execution_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    """Immutable safety verdict."""

    allowed: bool
    block: SafetyBlock
    reason: str


class IndependentSafetyGate:
    """Evaluate non-model safety conditions before execution routing."""

    def evaluate(self, state: SafetyState) -> SafetyDecision:
        if not isinstance(state, SafetyState):
            raise TypeError("state must be a SafetyState")

        checks = (
            (state.kill_switch_active, SafetyBlock.KILL_SWITCH, "Independent kill switch is active."),
            (state.stale_data, SafetyBlock.STALE_DATA, "Market data is stale."),
            (not state.data_quality_ok, SafetyBlock.DATA_QUALITY, "Market data quality is not valid."),
            (not state.session_open, SafetyBlock.SESSION_CLOSED, "Trading session is closed."),
        )

        for blocked, block, reason in checks:
            if blocked:
                return SafetyDecision(False, block, reason)

        if not state.live_execution_enabled:
            return SafetyDecision(
                False,
                SafetyBlock.LIVE_LOCKED,
                "Live execution remains locked by the trading specification.",
            )

        return SafetyDecision(True, SafetyBlock.NONE, "Independent safety checks passed.")
