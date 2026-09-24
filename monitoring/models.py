"""Immutable contracts for the STOCK_BOT monitoring engine.

The monitoring layer observes system state. It does not authorize trades,
change risk, mutate models, or enable live execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def fingerprint(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 fingerprint for an event payload."""
    encoded = json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


class ComponentHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class MonitoringEvent:
    """Immutable telemetry event emitted by any STOCK_BOT component."""

    event_id: str
    timestamp: datetime
    event_type: str
    source: str
    severity: AlertSeverity = AlertSeverity.INFO
    symbol: str | None = None
    correlation_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("event timestamp must be timezone-aware")
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty")
        if not self.source.strip():
            raise ValueError("source must not be empty")
        object.__setattr__(self, "payload", dict(self.payload))

    @property
    def fingerprint(self) -> str:
        return fingerprint(
            {
                "event_id": self.event_id,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "source": self.source,
                "severity": self.severity,
                "symbol": self.symbol,
                "correlation_id": self.correlation_id,
                "payload": self.payload,
            }
        )


@dataclass(frozen=True, slots=True)
class Alert:
    """Immutable monitoring alert."""

    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    code: str
    source: str
    message: str
    correlation_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("alert timestamp must be timezone-aware")
        if not self.alert_id.strip() or not self.code.strip() or not self.source.strip():
            raise ValueError("alert identity fields must not be empty")
        if not self.message.strip():
            raise ValueError("alert message must not be empty")
        object.__setattr__(self, "details", dict(self.details))

    @property
    def fingerprint(self) -> str:
        return fingerprint(
            {
                "alert_id": self.alert_id,
                "timestamp": self.timestamp,
                "severity": self.severity,
                "code": self.code,
                "source": self.source,
                "message": self.message,
                "correlation_id": self.correlation_id,
                "details": self.details,
            }
        )


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Immutable distribution-drift measurement."""

    metric: str
    reference_count: int
    current_count: int
    value: float
    threshold: float
    exceeded: bool
    method: str = "PSI"

    def __post_init__(self) -> None:
        if self.reference_count < 0 or self.current_count < 0:
            raise ValueError("drift sample counts must be non-negative")
        if not math.isfinite(self.value) or not math.isfinite(self.threshold):
            raise ValueError("drift values must be finite")
        if self.threshold < 0:
            raise ValueError("drift threshold must be non-negative")


@dataclass(frozen=True, slots=True)
class SystemHealth:
    """Immutable aggregate health snapshot."""

    timestamp: datetime
    overall: ComponentHealth
    components: Mapping[str, ComponentHealth]
    heartbeat_age_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("health timestamp must be timezone-aware")
        if self.heartbeat_age_seconds is not None and self.heartbeat_age_seconds < 0:
            raise ValueError("heartbeat_age_seconds must not be negative")
        object.__setattr__(self, "components", dict(self.components))


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """Point-in-time cross-domain monitoring snapshot."""

    timestamp: datetime
    data_freshness_seconds: float | None = None
    missing_candles: int = 0
    duplicate_events: int = 0
    feed_latency_ms: float | None = None
    feature_missing_rate: float | None = None
    feature_inf_rate: float | None = None
    error_rate: float | None = None
    stale_rate: float | None = None
    prediction_psi: float | None = None
    model_accuracy: float | None = None
    model_log_loss: float | None = None
    signal_count: int = 0
    no_trade_count: int = 0
    trade_count: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    gross_exposure_pct: float = 0.0
    open_positions: int = 0
    entries_today: int = 0
    execution_latency_ms: float | None = None
    slippage_bps: float | None = None
    order_rejection_rate: float | None = None
    reconciliation_mismatch: bool = False

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("snapshot timestamp must be timezone-aware")
        integer_fields = (
            self.missing_candles,
            self.duplicate_events,
            self.signal_count,
            self.no_trade_count,
            self.trade_count,
            self.open_positions,
            self.entries_today,
        )
        if any(value < 0 for value in integer_fields):
            raise ValueError("monitoring counters must be non-negative")
        for value in (
            self.data_freshness_seconds,
            self.feed_latency_ms,
            self.feature_missing_rate,
            self.feature_inf_rate,
            self.error_rate,
            self.stale_rate,
            self.prediction_psi,
            self.model_accuracy,
            self.model_log_loss,
            self.realized_pnl,
            self.unrealized_pnl,
            self.drawdown_pct,
            self.gross_exposure_pct,
            self.execution_latency_ms,
            self.slippage_bps,
            self.order_rejection_rate,
        ):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("monitoring numeric values must be finite")

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl
