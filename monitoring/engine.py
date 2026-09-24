"""Production monitoring engine for STOCK_BOT.

The engine aggregates telemetry across data, features, model, strategy,
risk, execution and paper-trading domains. It is observational only.
Safety decisions remain in the independent execution safety layer.

References:
    - STOCK_BOT Phase 23 monitoring requirements.
    - execution.safety and execution.control.
    - journal TradeDecisionRecord / TradeJournalRecord.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import uuid
from typing import Iterable, Mapping, Sequence

from monitoring.drift import population_stability_index
from monitoring.models import (
    Alert,
    AlertSeverity,
    ComponentHealth,
    MonitoringEvent,
    MonitoringSnapshot,
    SystemHealth,
)
from monitoring.rules import MonitoringPolicy
from monitoring.store import MonitoringStore


class MonitoringEngine:
    """Collect, evaluate and persist STOCK_BOT telemetry."""

    def __init__(
        self,
        *,
        policy: MonitoringPolicy | None = None,
        store: MonitoringStore | None = None,
    ) -> None:
        self.policy = policy or MonitoringPolicy()
        self.store = store or MonitoringStore()

    def emit(
        self,
        *,
        event_type: str,
        source: str,
        payload: Mapping,
        severity: AlertSeverity = AlertSeverity.INFO,
        symbol: str | None = None,
        correlation_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> MonitoringEvent:
        """Persist a single monitoring event."""
        event = MonitoringEvent(
            event_id=str(uuid.uuid4()),
            timestamp=timestamp or datetime.now(timezone.utc),
            event_type=event_type,
            source=source,
            severity=severity,
            symbol=symbol,
            correlation_id=correlation_id,
            payload=dict(payload),
        )
        self.store.append_event(event)
        return event

    def inspect_snapshot(
        self,
        snapshot: MonitoringSnapshot,
        *,
        source: str = "monitoring_engine",
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Evaluate one point-in-time telemetry snapshot."""
        if not isinstance(snapshot, MonitoringSnapshot):
            raise TypeError("snapshot must be MonitoringSnapshot")

        alerts: list[Alert] = []

        def check(
            condition: bool,
            *,
            severity: AlertSeverity,
            code: str,
            message: str,
            details: Mapping,
        ) -> None:
            if not condition:
                return
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                timestamp=snapshot.timestamp,
                severity=severity,
                code=code,
                source=source,
                message=message,
                correlation_id=correlation_id,
                details=dict(details),
            )
            self.store.append_alert(alert)
            alerts.append(alert)

        if snapshot.data_freshness_seconds is not None:
            check(
                snapshot.data_freshness_seconds > self.policy.max_data_freshness_seconds,
                severity=AlertSeverity.CRITICAL,
                code="DATA_STALE",
                message="Market data freshness exceeded monitoring threshold.",
                details={"value": snapshot.data_freshness_seconds, "threshold": self.policy.max_data_freshness_seconds},
            )
        check(
            snapshot.missing_candles > 0,
            severity=AlertSeverity.CRITICAL,
            code="MISSING_CANDLES",
            message="Missing market candles detected.",
            details={"count": snapshot.missing_candles},
        )
        check(
            snapshot.duplicate_events > 0,
            severity=AlertSeverity.CRITICAL,
            code="DUPLICATE_EVENTS",
            message="Duplicate market events detected.",
            details={"count": snapshot.duplicate_events},
        )
        if snapshot.feed_latency_ms is not None:
            check(
                snapshot.feed_latency_ms > self.policy.max_feed_latency_ms,
                severity=AlertSeverity.WARNING,
                code="FEED_LATENCY_HIGH",
                message="Market-feed latency exceeded threshold.",
                details={"value_ms": snapshot.feed_latency_ms, "threshold_ms": self.policy.max_feed_latency_ms},
            )
        if snapshot.feature_missing_rate is not None:
            check(
                snapshot.feature_missing_rate > self.policy.max_feature_missing_rate,
                severity=AlertSeverity.CRITICAL,
                code="FEATURE_MISSING_RATE_HIGH",
                message="Feature missing-rate exceeded threshold.",
                details={"value": snapshot.feature_missing_rate, "threshold": self.policy.max_feature_missing_rate},
            )
        if snapshot.feature_inf_rate is not None:
            check(
                snapshot.feature_inf_rate > self.policy.max_feature_inf_rate,
                severity=AlertSeverity.CRITICAL,
                code="FEATURE_INFINITY_RATE_HIGH",
                message="Feature infinity-rate exceeded threshold.",
                details={"value": snapshot.feature_inf_rate, "threshold": self.policy.max_feature_inf_rate},
            )
        if snapshot.error_rate is not None:
            check(
                snapshot.error_rate > self.policy.max_error_rate,
                severity=AlertSeverity.CRITICAL,
                code="ERROR_RATE_HIGH",
                message="Operational error-rate exceeded threshold.",
                details={"value": snapshot.error_rate, "threshold": self.policy.max_error_rate},
            )
        if snapshot.stale_rate is not None:
            check(
                snapshot.stale_rate > self.policy.max_stale_rate,
                severity=AlertSeverity.CRITICAL,
                code="STALE_RATE_HIGH",
                message="Stale-event rate exceeded threshold.",
                details={"value": snapshot.stale_rate, "threshold": self.policy.max_stale_rate},
            )
        if snapshot.prediction_psi is not None:
            check(
                snapshot.prediction_psi > self.policy.max_prediction_psi,
                severity=AlertSeverity.WARNING,
                code="PREDICTION_DRIFT",
                message="Prediction distribution drift exceeded threshold.",
                details={"psi": snapshot.prediction_psi, "threshold": self.policy.max_prediction_psi},
            )
        if snapshot.model_accuracy is not None and self.policy.min_model_accuracy > 0:
            check(
                snapshot.model_accuracy < self.policy.min_model_accuracy,
                severity=AlertSeverity.WARNING,
                code="MODEL_ACCURACY_LOW",
                message="Observed model accuracy is below monitoring floor.",
                details={"value": snapshot.model_accuracy, "threshold": self.policy.min_model_accuracy},
            )
        if snapshot.model_log_loss is not None:
            check(
                snapshot.model_log_loss > self.policy.max_model_log_loss,
                severity=AlertSeverity.WARNING,
                code="MODEL_LOG_LOSS_HIGH",
                message="Observed model log loss exceeded monitoring threshold.",
                details={"value": snapshot.model_log_loss, "threshold": self.policy.max_model_log_loss},
            )

        check(
            snapshot.drawdown_pct > self.policy.max_drawdown_pct,
            severity=AlertSeverity.CRITICAL,
            code="DRAWDOWN_HIGH",
            message="Observed drawdown exceeded monitoring threshold.",
            details={"value_pct": snapshot.drawdown_pct, "threshold_pct": self.policy.max_drawdown_pct},
        )
        check(
            snapshot.gross_exposure_pct > self.policy.max_gross_exposure_pct,
            severity=AlertSeverity.CRITICAL,
            code="GROSS_EXPOSURE_HIGH",
            message="Observed gross exposure exceeded monitoring threshold.",
            details={"value_pct": snapshot.gross_exposure_pct, "threshold_pct": self.policy.max_gross_exposure_pct},
        )
        check(
            snapshot.open_positions > self.policy.max_open_positions,
            severity=AlertSeverity.EMERGENCY,
            code="OPEN_POSITION_LIMIT_BREACH",
            message="Observed open positions exceed configured monitoring limit.",
            details={"value": snapshot.open_positions, "threshold": self.policy.max_open_positions},
        )
        check(
            snapshot.entries_today > self.policy.max_entries_today,
            severity=AlertSeverity.EMERGENCY,
            code="ENTRY_LIMIT_BREACH",
            message="Observed entries today exceed configured monitoring limit.",
            details={"value": snapshot.entries_today, "threshold": self.policy.max_entries_today},
        )

        if snapshot.execution_latency_ms is not None:
            check(
                snapshot.execution_latency_ms > self.policy.max_execution_latency_ms,
                severity=AlertSeverity.WARNING,
                code="EXECUTION_LATENCY_HIGH",
                message="Execution latency exceeded monitoring threshold.",
                details={"value_ms": snapshot.execution_latency_ms, "threshold_ms": self.policy.max_execution_latency_ms},
            )
        if snapshot.slippage_bps is not None:
            check(
                snapshot.slippage_bps > self.policy.max_slippage_bps,
                severity=AlertSeverity.WARNING,
                code="SLIPPAGE_HIGH",
                message="Observed slippage exceeded monitoring threshold.",
                details={"value_bps": snapshot.slippage_bps, "threshold_bps": self.policy.max_slippage_bps},
            )
        if snapshot.order_rejection_rate is not None:
            check(
                snapshot.order_rejection_rate > self.policy.max_order_rejection_rate,
                severity=AlertSeverity.CRITICAL,
                code="ORDER_REJECTION_RATE_HIGH",
                message="Order rejection rate exceeded monitoring threshold.",
                details={"value": snapshot.order_rejection_rate, "threshold": self.policy.max_order_rejection_rate},
            )
        check(
            snapshot.reconciliation_mismatch,
            severity=AlertSeverity.EMERGENCY,
            code="POSITION_RECONCILIATION_MISMATCH",
            message="Local and authoritative broker position state do not reconcile.",
            details={},
        )

        self.emit(
            event_type="MONITORING_SNAPSHOT",
            source=source,
            correlation_id=correlation_id,
            timestamp=snapshot.timestamp,
            payload={
                "total_pnl": snapshot.total_pnl,
                "alerts": [item.code for item in alerts],
                "signal_count": snapshot.signal_count,
                "trade_count": snapshot.trade_count,
            },
        )
        return tuple(alerts)

    def build_health(
        self,
        components: Mapping[str, ComponentHealth | str],
        *,
        heartbeat_age_seconds: float | None = None,
        timestamp: datetime | None = None,
    ) -> SystemHealth:
        """Build aggregate health without making execution decisions."""
        normalized = {
            name: value if isinstance(value, ComponentHealth) else ComponentHealth(value)
            for name, value in components.items()
        }
        if any(value is ComponentHealth.FAILED for value in normalized.values()):
            overall = ComponentHealth.FAILED
        elif any(value in {ComponentHealth.DEGRADED, ComponentHealth.UNKNOWN} for value in normalized.values()):
            overall = ComponentHealth.DEGRADED
        else:
            overall = ComponentHealth.HEALTHY
        health = SystemHealth(
            timestamp=timestamp or datetime.now(timezone.utc),
            overall=overall,
            components=normalized,
            heartbeat_age_seconds=heartbeat_age_seconds,
        )
        self.emit(
            event_type="SYSTEM_HEALTH",
            source="monitoring_engine",
            timestamp=health.timestamp,
            payload={
                "overall": health.overall.value,
                "components": {name: state.value for name, state in normalized.items()},
                "heartbeat_age_seconds": heartbeat_age_seconds,
            },
        )
        return health

    def prediction_drift(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        *,
        threshold: float | None = None,
    ):
        """Measure prediction drift without deciding model promotion."""
        value = population_stability_index(reference, current)
        selected_threshold = self.policy.max_prediction_psi if threshold is None else threshold
        return {
            "metric": "prediction_psi",
            "value": value,
            "threshold": selected_threshold,
            "exceeded": value > selected_threshold,
        }

    def class_distribution(self, predictions: Iterable[str]) -> Mapping[str, int]:
        """Count observed prediction classes for dashboard/reporting use."""
        return dict(Counter(predictions))

    def alerts(self) -> tuple[Alert, ...]:
        return self.store.read_alerts()

    def events(self) -> tuple[MonitoringEvent, ...]:
        return self.store.read_events()
