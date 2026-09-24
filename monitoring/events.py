"""Structured monitoring events for STOCK_BOT.

The event layer is observational. It must never authorize, reject, resize,
or execute a trade.

References:
    docs/MONITORING_ENGINE.md
    docs/PHASE_9_SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MonitoringEventType(StrEnum):
    """Canonical telemetry event types."""

    SYSTEM_HEARTBEAT = "SYSTEM_HEARTBEAT"
    DATA_QUALITY = "DATA_QUALITY"
    FEATURE_HEALTH = "FEATURE_HEALTH"
    PREDICTION = "PREDICTION"
    DECISION = "DECISION"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    OUTCOME = "OUTCOME"
    DRIFT = "DRIFT"
    ALERT = "ALERT"


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    """Immutable event envelope used across monitoring boundaries."""

    event_type: MonitoringEventType | str
    source: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    symbol: str | None = None
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        """Validate identity and timestamp invariants."""
        if not self.source.strip():
            raise ValueError("source must be non-empty")
        if self.symbol is not None and not self.symbol.strip():
            raise ValueError("symbol must be non-empty when provided")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if not self.event_id.strip():
            raise ValueError("event_id must be non-empty")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id must be non-empty")

    @classmethod
    def now(
        cls,
        event_type: MonitoringEventType | str,
        source: str,
        payload: dict[str, Any] | None = None,
        *,
        symbol: str | None = None,
        correlation_id: str | None = None,
    ) -> "MonitoringEvent":
        """Create an event stamped with UTC wall-clock time."""
        return cls(
            event_type=event_type,
            source=source,
            timestamp=datetime.now(timezone.utc),
            payload=dict(payload or {}),
            symbol=symbol,
            correlation_id=correlation_id or str(uuid4()),
        )
