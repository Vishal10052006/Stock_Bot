"""Phase 21 live signal engine.

Consumes validated decision-time StrategyInput objects, enforces session and
chronology controls, and delegates quantitative decisions to StrategyEngine.
This module has no Risk, Execution, or broker authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import Enum
import hashlib
import math
from zoneinfo import ZoneInfo

import pandas as pd

from trading.strategy.engine import StrategyEngine
from trading.strategy.models import (
    NoTradeReason,
    StrategyDecision,
    StrategyDirection,
    StrategyInput,
)


IST = ZoneInfo("Asia/Kolkata")


class LiveSignalStatus(str, Enum):
    SIGNAL = "SIGNAL"
    NO_TRADE = "NO_TRADE"
    BLOCKED = "BLOCKED"


class LiveSignalBlockReason(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    FUTURE_INPUT = "FUTURE_INPUT"
    STALE_INPUT = "STALE_INPUT"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    DUPLICATE = "DUPLICATE"
    OUTSIDE_SESSION = "OUTSIDE_SESSION"


@dataclass(frozen=True, slots=True)
class LiveSignalEvent:
    """Immutable, auditable output of one live-signal evaluation."""

    event_id: str
    timestamp: pd.Timestamp
    symbol: str
    status: LiveSignalStatus
    decision: StrategyDecision
    block_reason: LiveSignalBlockReason | None = None

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("live signal timestamp must be timezone-aware")
        if not self.symbol.strip():
            raise ValueError("live signal symbol must not be empty")
        if self.status is LiveSignalStatus.BLOCKED and self.block_reason is None:
            raise ValueError("blocked live signal must include block_reason")
        if self.status is not LiveSignalStatus.BLOCKED and self.block_reason is not None:
            raise ValueError("non-blocked live signal must not include block_reason")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


class LiveSignalEngine:
    """Produce causal live signals without sizing or execution authority."""

    VERSION = "LIVE-SIGNAL-v1.0"

    def __init__(
        self,
        *,
        strategy_engine: StrategyEngine | None = None,
        max_staleness_seconds: float = 300.0,
        session_start: time = time(9, 15),
        session_end: time = time(15, 30),
    ) -> None:
        if not math.isfinite(max_staleness_seconds) or max_staleness_seconds < 0:
            raise ValueError("max_staleness_seconds must be finite and non-negative")
        if not isinstance(session_start, time) or not isinstance(session_end, time):
            raise TypeError("session_start and session_end must be datetime.time values")
        if session_start >= session_end:
            raise ValueError("session_start must be before session_end")

        self.strategy_engine = strategy_engine or StrategyEngine()
        self.max_staleness_seconds = float(max_staleness_seconds)
        self.session_start = session_start
        self.session_end = session_end
        self._last_timestamp: dict[str, pd.Timestamp] = {}

    def evaluate(
        self,
        strategy_input: StrategyInput,
        *,
        observed_at: pd.Timestamp,
    ) -> LiveSignalEvent:
        """Evaluate one decision-time input against live-data boundaries.

        observed_at is explicit so tests and paper runs can reproduce the
        exact staleness decision without consulting an implicit system clock.
        """
        if not isinstance(strategy_input, StrategyInput):
            return self._blocked_from_invalid_input(strategy_input)

        try:
            timestamp = pd.Timestamp(strategy_input.timestamp)
            observed = pd.Timestamp(observed_at)
            symbol = str(strategy_input.symbol).strip().upper()
            if timestamp.tzinfo is None or observed.tzinfo is None:
                return self._blocked(
                    strategy_input,
                    LiveSignalBlockReason.INVALID_INPUT,
                )
            if not symbol:
                return self._blocked(
                    strategy_input,
                    LiveSignalBlockReason.INVALID_INPUT,
                )
        except (AttributeError, TypeError, ValueError):
            return self._blocked_from_invalid_input(strategy_input)

        timestamp = timestamp.tz_convert(IST)
        observed = observed.tz_convert(IST)

        if observed < timestamp:
            return self._blocked(
                strategy_input,
                LiveSignalBlockReason.FUTURE_INPUT,
            )

        age_seconds = (observed - timestamp).total_seconds()
        if age_seconds > self.max_staleness_seconds:
            return self._blocked(
                strategy_input,
                LiveSignalBlockReason.STALE_INPUT,
            )

        local_time = timestamp.timetz().replace(tzinfo=None)
        if not self.session_start <= local_time <= self.session_end:
            return self._blocked(
                strategy_input,
                LiveSignalBlockReason.OUTSIDE_SESSION,
            )

        previous = self._last_timestamp.get(symbol)
        if previous is not None:
            if timestamp < previous:
                return self._blocked(
                    strategy_input,
                    LiveSignalBlockReason.OUT_OF_ORDER,
                )
            if timestamp == previous:
                return self._blocked(
                    strategy_input,
                    LiveSignalBlockReason.DUPLICATE,
                )

        try:
            decision, _trace = self.strategy_engine.decide(strategy_input)
        except (TypeError, ValueError):
            return self._blocked(
                strategy_input,
                LiveSignalBlockReason.INVALID_INPUT,
            )

        self._last_timestamp[symbol] = timestamp

        status = (
            LiveSignalStatus.SIGNAL
            if decision.direction is not StrategyDirection.NO_TRADE
            else LiveSignalStatus.NO_TRADE
        )
        return self._event(
            strategy_input,
            status=status,
            decision=decision,
        )

    def last_timestamp(self, symbol: str) -> pd.Timestamp | None:
        """Return the latest accepted decision timestamp for one symbol."""
        return self._last_timestamp.get(symbol.strip().upper())

    @staticmethod
    def _event(
        strategy_input: StrategyInput,
        *,
        status: LiveSignalStatus,
        decision: StrategyDecision,
        block_reason: LiveSignalBlockReason | None = None,
    ) -> LiveSignalEvent:
        timestamp = pd.Timestamp(strategy_input.timestamp)
        symbol = str(strategy_input.symbol).strip().upper()
        primary_reason = (
            decision.primary_reason.value if decision.primary_reason else ""
        )
        payload = (
            f"{LiveSignalEngine.VERSION}|{timestamp.isoformat()}|{symbol}|"
            f"{status.value}|{decision.strategy_version}|"
            f"{decision.direction.value}|{primary_reason}"
        )
        event_id = "SIG-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
        return LiveSignalEvent(
            event_id=event_id,
            timestamp=timestamp,
            symbol=symbol,
            status=status,
            decision=decision,
            block_reason=block_reason,
        )

    @classmethod
    def _blocked(
        cls,
        strategy_input: StrategyInput,
        reason: LiveSignalBlockReason,
    ) -> LiveSignalEvent:
        decision = StrategyDecision(
            timestamp=pd.Timestamp(strategy_input.timestamp),
            symbol=str(strategy_input.symbol),
            direction=StrategyDirection.NO_TRADE,
            strategy_version=cls.VERSION,
            rationale=reason.value,
            primary_reason=NoTradeReason.INVALID_INPUT,
            provenance={"live_signal_block": reason.value},
        )
        return cls._event(
            strategy_input,
            status=LiveSignalStatus.BLOCKED,
            decision=decision,
            block_reason=reason,
        )

    @classmethod
    def _blocked_from_invalid_input(
        cls,
        strategy_input: object,
    ) -> LiveSignalEvent:
        """Construct a safe block even when the input object is malformed."""
        timestamp = getattr(
            strategy_input,
            "timestamp",
            pd.Timestamp("1970-01-01", tz="UTC"),
        )
        symbol = str(getattr(strategy_input, "symbol", "UNKNOWN") or "UNKNOWN").strip()
        if not symbol:
            symbol = "UNKNOWN"
        try:
            timestamp = pd.Timestamp(timestamp)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize("UTC")
        except (TypeError, ValueError):
            timestamp = pd.Timestamp("1970-01-01", tz="UTC")

        safe_input = StrategyInput(
            timestamp=timestamp,
            symbol=symbol,
            decision_features={},
            regime="INVALID",
            regime_probability=0.0,
        )
        return cls._blocked(safe_input, LiveSignalBlockReason.INVALID_INPUT)


__all__ = [
    "IST",
    "LiveSignalBlockReason",
    "LiveSignalEngine",
    "LiveSignalEvent",
    "LiveSignalStatus",
]
