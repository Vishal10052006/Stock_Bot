"""Canonical contracts for the STOCK_BOT automation control plane."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
import hashlib
import json
import uuid


class AutomationMode(str, Enum):
    """Supported automation modes."""

    PAPER = "paper"
    SHADOW = "shadow"
    READINESS = "readiness"


class RunStatus(str, Enum):
    """Lifecycle state for one automated run."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class Stage(str, Enum):
    """Canonical stages; business logic remains in existing engines."""

    DATA = "DATA"
    RESEARCH = "RESEARCH"
    MARKET = "MARKET"
    ANALYSIS = "ANALYSIS"
    PREDICTION = "PREDICTION"
    STRATEGY = "STRATEGY"
    RISK = "RISK"
    SAFETY = "SAFETY"
    EXECUTION = "EXECUTION"
    MONITORING = "MONITORING"
    LEARNING = "LEARNING"


@dataclass(frozen=True, slots=True)
class StageEvent:
    """Immutable stage event for lineage and observability."""

    run_id: str
    stage: Stage
    event_type: str
    timestamp: datetime
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("StageEvent.timestamp must be timezone-aware")
        object.__setattr__(self, "payload", dict(self.payload))


@dataclass(frozen=True, slots=True)
class RunContext:
    """Immutable execution envelope shared across the automation graph."""

    run_id: str
    decision_timestamp: datetime
    symbol: str
    timeframe_minutes: int = 5
    mode: AutomationMode = AutomationMode.PAPER
    versions: Mapping[str, str] = field(default_factory=dict)
    status: RunStatus = RunStatus.CREATED
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        symbol: str,
        decision_timestamp: datetime,
        mode: AutomationMode = AutomationMode.PAPER,
        timeframe_minutes: int = 5,
        versions: Mapping[str, str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "RunContext":
        """Create a causally identified run."""
        if decision_timestamp.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware")
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        if timeframe_minutes <= 0:
            raise ValueError("timeframe_minutes must be positive")
        return cls(
            run_id=str(uuid.uuid4()),
            decision_timestamp=decision_timestamp.astimezone(timezone.utc),
            symbol=normalized,
            timeframe_minutes=timeframe_minutes,
            mode=mode,
            versions=dict(versions or {}),
            metadata=dict(metadata or {}),
        )

    def with_status(self, status: RunStatus) -> "RunContext":
        """Return a new immutable context with an updated status."""
        return RunContext(
            run_id=self.run_id,
            decision_timestamp=self.decision_timestamp,
            symbol=self.symbol,
            timeframe_minutes=self.timeframe_minutes,
            mode=self.mode,
            versions=self.versions,
            status=status,
            metadata=self.metadata,
        )

    @property
    def idempotency_key(self) -> str:
        """Stable logical identity for a decision point."""
        payload = {
            "symbol": self.symbol,
            "timestamp": self.decision_timestamp.isoformat(),
            "timeframe_minutes": self.timeframe_minutes,
            "mode": self.mode.value,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class AutomationResult:
    """Immutable result returned by the orchestrator."""

    run: RunContext
    events: tuple[StageEvent, ...]
    outputs: Mapping[Stage, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", dict(self.outputs))
