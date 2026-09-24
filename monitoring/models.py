"""Immutable contracts for the STOCK_BOT monitoring engine.

M-1 System, M-2 Market Data, M-3 Features, M-4 Model, M-5 Strategy,
M-6 Risk, M-7 Execution, and M-8 Outcome/Learning all report through these
common contracts.

Monitoring is observational. It never grants trading authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _canonical(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical(item) for item in value)
    return value


def fingerprint(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 fingerprint."""
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
    """Immutable telemetry event emitted by any subsystem."""

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
        if not self.event_id.strip() or not self.event_type.strip() or not self.source.strip():
            raise ValueError("event identity fields must not be empty")
        object.__setattr__(self, "severity", AlertSeverity(self.severity))
        object.__setattr__(self, "payload", dict(self.payload))


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
        object.__setattr__(self, "severity", AlertSeverity(self.severity))
        object.__setattr__(self, "details", dict(self.details))


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
        if not self.metric.strip() or not self.method.strip():
            raise ValueError("drift identity fields must not be empty")


@dataclass(frozen=True, slots=True)
class SystemHealth:
    """Aggregate M-1 system health snapshot."""

    timestamp: datetime
    overall: ComponentHealth
    components: Mapping[str, ComponentHealth]
    heartbeat_age_seconds: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("health timestamp must be timezone-aware")
        if self.heartbeat_age_seconds is not None:
            if self.heartbeat_age_seconds < 0 or not math.isfinite(self.heartbeat_age_seconds):
                raise ValueError("heartbeat_age_seconds must be finite and non-negative")
        object.__setattr__(self, "overall", ComponentHealth(self.overall))
        object.__setattr__(
            self,
            "components",
            {
                str(name): (
                    state if isinstance(state, ComponentHealth)
                    else ComponentHealth(str(state))
                )
                for name, state in self.components.items()
            },
        )


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    """Reusable M-4/M-5/M-8 performance summary."""

    trade_count: int
    winning_trades: int
    losing_trades: int
    net_pnl: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    expectancy: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    average_holding_minutes: float
    average_mae: float
    average_mfe: float

    def __post_init__(self) -> None:
        if self.trade_count < 0 or self.winning_trades < 0 or self.losing_trades < 0:
            raise ValueError("trade counts must be non-negative")
        if self.winning_trades + self.losing_trades > self.trade_count:
            raise ValueError("winning and losing counts exceed trade count")
        for name, value in (
            ("win_rate", self.win_rate),
            ("expectancy", self.expectancy),
            ("net_pnl", self.net_pnl),
            ("gross_pnl", self.gross_pnl),
            ("fees", self.fees),
            ("slippage_cost", self.slippage_cost),
            ("max_drawdown", self.max_drawdown),
            ("average_holding_minutes", self.average_holding_minutes),
            ("average_mae", self.average_mae),
            ("average_mfe", self.average_mfe),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not math.isfinite(float(self.profit_factor)) and not math.isinf(float(self.profit_factor)):
            raise ValueError("profit_factor must be numeric")


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """Cross-domain point-in-time monitoring snapshot.

    Risk-limit values mirror the frozen research/paper specification only as
    observational reference values. The Risk Engine remains authoritative.
    """

    timestamp: datetime

    # M-1 System
    system_health: ComponentHealth = ComponentHealth.HEALTHY
    heartbeat_age_seconds: float | None = None

    # M-2 Market Data
    data_freshness_seconds: float | None = None
    missing_candles: int = 0
    duplicate_events: int = 0
    feed_latency_ms: float | None = None
    invalid_ohlc_count: int = 0
    connection_failures: int = 0
    reconnect_count: int = 0
    clock_drift_ms: float | None = None

    # M-3 Features
    feature_missing_rate: float | None = None
    feature_inf_rate: float | None = None
    feature_stale_rate: float | None = None
    feature_drift_count: int = 0

    # M-4 Model
    error_rate: float | None = None
    stale_rate: float | None = None
    prediction_psi: float | None = None
    model_accuracy: float | None = None
    model_balanced_accuracy: float | None = None
    model_f1: float | None = None
    model_log_loss: float | None = None
    model_brier_score: float | None = None
    calibration_error: float | None = None

    # M-5 Strategy
    signal_count: int = 0
    no_trade_count: int = 0
    trade_count: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    expectancy: float | None = None
    win_rate: float | None = None
    profit_factor: float | None = None
    max_drawdown_pct: float = 0.0

    # M-6 Risk
    daily_pnl: float = 0.0
    daily_loss_pct: float = 0.0
    gross_exposure_pct: float = 0.0
    open_positions: int = 0
    entries_today: int = 0
    risk_utilization_pct: float | None = None
    kill_switch_active: bool = False

    # M-7 Execution
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    partial_fill_count: int = 0
    execution_latency_ms: float | None = None
    slippage_bps: float | None = None
    order_rejection_rate: float | None = None
    reconciliation_mismatch: bool = False

    # M-8 Outcome / Learning
    completed_outcomes: int = 0
    journal_linked_outcomes: int = 0
    learning_experiences: int = 0
    candidate_proposals: int = 0

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("snapshot timestamp must be timezone-aware")

        integer_fields = (
            self.missing_candles,
            self.duplicate_events,
            self.invalid_ohlc_count,
            self.connection_failures,
            self.reconnect_count,
            self.feature_drift_count,
            self.signal_count,
            self.no_trade_count,
            self.trade_count,
            self.open_positions,
            self.entries_today,
            self.orders_submitted,
            self.orders_filled,
            self.orders_rejected,
            self.partial_fill_count,
            self.completed_outcomes,
            self.journal_linked_outcomes,
            self.learning_experiences,
            self.candidate_proposals,
        )
        if any(value < 0 for value in integer_fields):
            raise ValueError("monitoring counters must be non-negative")

        for value in (
            self.heartbeat_age_seconds,
            self.data_freshness_seconds,
            self.feed_latency_ms,
            self.clock_drift_ms,
            self.feature_missing_rate,
            self.feature_inf_rate,
            self.feature_stale_rate,
            self.error_rate,
            self.stale_rate,
            self.prediction_psi,
            self.model_accuracy,
            self.model_balanced_accuracy,
            self.model_f1,
            self.model_log_loss,
            self.model_brier_score,
            self.calibration_error,
            self.realized_pnl,
            self.unrealized_pnl,
            self.expectancy,
            self.win_rate,
            self.profit_factor,
            self.max_drawdown_pct,
            self.daily_pnl,
            self.daily_loss_pct,
            self.gross_exposure_pct,
            self.risk_utilization_pct,
            self.execution_latency_ms,
            self.slippage_bps,
            self.order_rejection_rate,
        ):
            if value is not None and not math.isfinite(float(value)) and value is not self.profit_factor:
                raise ValueError("monitoring numeric values must be finite")

        if self.orders_filled + self.orders_rejected > self.orders_submitted:
            raise ValueError("filled + rejected orders cannot exceed submitted orders")

        object.__setattr__(self, "system_health", ComponentHealth(self.system_health))

    @property
    def total_pnl(self) -> float:
        """Return realized plus unrealized P&L."""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def fill_rate(self) -> float | None:
        """Return order fill rate when there are submitted orders."""
        if self.orders_submitted == 0:
            return None
        return self.orders_filled / self.orders_submitted

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe snapshot data."""
        return _canonical(asdict(self))


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    """Dashboard-ready aggregate monitoring report."""

    timestamp: datetime
    system_health: SystemHealth
    snapshot: MonitoringSnapshot
    alerts: tuple[Alert, ...]
    drift: tuple[DriftReport, ...]

    @property
    def healthy(self) -> bool:
        return not self.alerts

    @property
    def critical(self) -> bool:
        return any(
            alert.severity in {AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY}
            for alert in self.alerts
        )

    def to_dict(self) -> dict[str, Any]:
        """Return dashboard/API-safe report data."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "healthy": self.healthy,
            "critical": self.critical,
            "system_health": {
                "overall": self.system_health.overall.value,
                "components": {
                    key: value.value
                    for key, value in self.system_health.components.items()
                },
                "heartbeat_age_seconds": self.system_health.heartbeat_age_seconds,
            },
            "snapshot": self.snapshot.to_dict(),
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "severity": alert.severity.value,
                    "code": alert.code,
                    "source": alert.source,
                    "message": alert.message,
                    "correlation_id": alert.correlation_id,
                    "details": _canonical(alert.details),
                }
                for alert in self.alerts
            ],
            "drift": [
                {
                    "metric": item.metric,
                    "reference_count": item.reference_count,
                    "current_count": item.current_count,
                    "value": item.value,
                    "threshold": item.threshold,
                    "exceeded": item.exceeded,
                    "method": item.method,
                }
                for item in self.drift
            ],
        }
