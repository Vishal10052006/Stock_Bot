"""Production monitoring engine for STOCK_BOT.

M-1 System -> M-2 Market Data -> M-3 Features -> M-4 Model ->
M-5 Strategy -> M-6 Risk -> M-7 Execution -> M-8 Outcome/Learning.

The engine observes and reports. It does not authorize orders, modify risk,
mutate strategy/model state, promote models, or enable live execution.

References:
    STOCK_BOT Phase 23 Continuous Model Monitoring.
    TRADING_SPECIFICATION.md.
    execution.safety / execution.control.
    journal.models.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence
import uuid

from monitoring.adapters import (
    decision_payload,
    outcome_payload,
    prediction_payload,
    reconciliation_payload,
    safety_payload,
)
from monitoring.alerting import AlertManager
from monitoring.drift import population_stability_index
from monitoring.health import HealthMonitor
from monitoring.metrics import MonitoringMetrics
from monitoring.models import (
    Alert,
    AlertSeverity,
    ComponentHealth,
    DriftReport,
    MonitoringEvent,
    MonitoringReport,
    MonitoringSnapshot,
    PerformanceSnapshot,
    SystemHealth,
)
from monitoring.performance import performance_from_records, grouped_net_pnl
from monitoring.reporting import build_trade_report
from monitoring.rules import MonitoringPolicy
from monitoring.store import MonitoringStore


class MonitoringEngine:
    """Collect, evaluate, persist and summarize STOCK_BOT telemetry."""

    def __init__(
        self,
        *,
        policy: MonitoringPolicy | None = None,
        store: MonitoringStore | None = None,
        alert_manager: AlertManager | None = None,
        health_monitor: HealthMonitor | None = None,
        metrics: MonitoringMetrics | None = None,
    ) -> None:
        self.policy = policy or MonitoringPolicy()
        self.store = store or MonitoringStore()
        self.alert_manager = alert_manager or AlertManager()
        self.health_monitor = health_monitor or HealthMonitor()
        self.metrics = metrics or MonitoringMetrics()

    # ------------------------------------------------------------------
    # M-1 SYSTEM
    # ------------------------------------------------------------------
    def heartbeat(
        self,
        component: str,
        *,
        timestamp: datetime | None = None,
    ) -> SystemHealth:
        """Record a component heartbeat and return current aggregate health."""
        heartbeat = self.health_monitor.heartbeat(
            component,
            timestamp=timestamp,
        )
        self.emit(
            event_type="SYSTEM_HEARTBEAT",
            source=heartbeat.component,
            timestamp=heartbeat.timestamp,
            payload={"component": heartbeat.component},
        )
        return self.health_monitor.health(timestamp=heartbeat.timestamp)

    def build_health(
        self,
        components: Mapping[str, ComponentHealth | str] | None = None,
        *,
        heartbeat_age_seconds: float | None = None,
        timestamp: datetime | None = None,
        expected_components: tuple[str, ...] = (),
        heartbeat_timeout_seconds: float = 30.0,
    ) -> SystemHealth:
        """Build aggregate M-1 health from explicit states or heartbeats."""
        if components is None:
            health = self.health_monitor.health(
                now=timestamp,
                timeout_seconds=heartbeat_timeout_seconds,
                expected_components=expected_components,
            )
        else:
            normalized = {
                name: (
                    value
                    if isinstance(value, ComponentHealth)
                    else ComponentHealth(str(value))
                )
                for name, value in components.items()
            }
            if any(state is ComponentHealth.FAILED for state in normalized.values()):
                overall = ComponentHealth.FAILED
            elif any(
                state in {ComponentHealth.DEGRADED, ComponentHealth.UNKNOWN}
                for state in normalized.values()
            ):
                overall = ComponentHealth.DEGRADED
            else:
                overall = ComponentHealth.HEALTHY
            health = SystemHealth(
                timestamp=timestamp or datetime.now(timezone.utc),
                overall=overall,
                components=normalized,
                heartbeat_age_seconds=heartbeat_age_seconds,
            )

        self.metrics.increment("system_health_snapshots")
        self.emit(
            event_type="SYSTEM_HEALTH",
            source="monitoring_engine",
            timestamp=health.timestamp,
            payload={
                "overall": health.overall.value,
                "components": {
                    name: state.value
                    for name, state in health.components.items()
                },
                "heartbeat_age_seconds": health.heartbeat_age_seconds,
            },
        )
        return health

    # ------------------------------------------------------------------
    # M-2 MARKET DATA
    # ------------------------------------------------------------------
    def observe_market_data(
        self,
        *,
        timestamp: datetime,
        symbol: str | None = None,
        freshness_seconds: float | None = None,
        missing_candles: int = 0,
        duplicate_events: int = 0,
        feed_latency_ms: float | None = None,
        invalid_ohlc_count: int = 0,
        connection_failures: int = 0,
        reconnect_count: int = 0,
        clock_drift_ms: float | None = None,
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Observe one market-data health sample."""
        self.metrics.increment("market_data_observations")
        self.metrics.increment("missing_candles", missing_candles)
        self.metrics.increment("duplicate_events", duplicate_events)
        self.metrics.increment("invalid_ohlc", invalid_ohlc_count)
        self.metrics.increment("connection_failures", connection_failures)
        self.metrics.increment("reconnects", reconnect_count)
        if feed_latency_ms is not None:
            self.metrics.observe("feed_latency_ms", feed_latency_ms)

        snapshot = MonitoringSnapshot(
            timestamp=timestamp,
            data_freshness_seconds=freshness_seconds,
            missing_candles=missing_candles,
            duplicate_events=duplicate_events,
            feed_latency_ms=feed_latency_ms,
            invalid_ohlc_count=invalid_ohlc_count,
            connection_failures=connection_failures,
            reconnect_count=reconnect_count,
            clock_drift_ms=clock_drift_ms,
        )
        return self.inspect_snapshot(
            snapshot,
            source="market_data",
            correlation_id=correlation_id or symbol,
        )

    # ------------------------------------------------------------------
    # M-3 FEATURES
    # ------------------------------------------------------------------
    def feature_drift(
        self,
        feature_name: str,
        reference: Sequence[float],
        current: Sequence[float],
        *,
        threshold: float | None = None,
    ) -> DriftReport:
        """Measure numeric feature drift using PSI."""
        value = population_stability_index(reference, current)
        selected_threshold = (
            self.policy.max_prediction_psi
            if threshold is None
            else threshold
        )
        report = DriftReport(
            metric=f"feature:{feature_name}",
            reference_count=len(reference),
            current_count=len(current),
            value=value,
            threshold=selected_threshold,
            exceeded=value > selected_threshold,
            method="PSI",
        )
        self.metrics.increment("feature_drift_checks")
        if report.exceeded:
            self.metrics.increment("feature_drift_breaches")
        return report

    def feature_batch_drift(
        self,
        reference: Mapping[str, Sequence[float]],
        current: Mapping[str, Sequence[float]],
        *,
        threshold: float | None = None,
    ) -> tuple[DriftReport, ...]:
        """Measure every feature present in both reference and current data."""
        reports: list[DriftReport] = []
        for name in sorted(set(reference) & set(current)):
            reports.append(
                self.feature_drift(
                    name,
                    reference[name],
                    current[name],
                    threshold=threshold,
                )
            )
        return tuple(reports)

    def observe_features(
        self,
        *,
        timestamp: datetime,
        missing_rate: float = 0.0,
        inf_rate: float = 0.0,
        stale_rate: float = 0.0,
        drift_reports: Sequence[DriftReport] = (),
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Observe feature quality and drift state."""
        snapshot = MonitoringSnapshot(
            timestamp=timestamp,
            feature_missing_rate=missing_rate,
            feature_inf_rate=inf_rate,
            feature_stale_rate=stale_rate,
            feature_drift_count=sum(report.exceeded for report in drift_reports),
        )
        alerts = list(
            self.inspect_snapshot(
                snapshot,
                source="feature_engine",
                correlation_id=correlation_id,
            )
        )
        for report in drift_reports:
            if report.exceeded:
                alert = self._alert(
                    timestamp=timestamp,
                    severity=AlertSeverity.WARNING,
                    code="FEATURE_DRIFT",
                    source="feature_engine",
                    message=f"Feature drift exceeded threshold: {report.metric}.",
                    correlation_id=correlation_id,
                    details={
                        "metric": report.metric,
                        "value": report.value,
                        "threshold": report.threshold,
                        "method": report.method,
                    },
                )
                if alert is not None:
                    alerts.append(alert)
        return tuple(alerts)

    # ------------------------------------------------------------------
    # M-4 MODEL
    # ------------------------------------------------------------------
    def prediction_drift(
        self,
        reference: Sequence[float],
        current: Sequence[float],
        *,
        threshold: float | None = None,
    ) -> dict[str, float | bool | int]:
        """Measure prediction distribution drift using PSI."""
        value = population_stability_index(reference, current)
        selected_threshold = (
            self.policy.max_prediction_psi
            if threshold is None
            else threshold
        )
        self.metrics.increment("prediction_drift_checks")
        if value > selected_threshold:
            self.metrics.increment("prediction_drift_breaches")
        return {
            "metric": "prediction_psi",
            "reference_count": len(reference),
            "current_count": len(current),
            "value": value,
            "threshold": selected_threshold,
            "exceeded": value > selected_threshold,
        }

    def observe_model_prediction(
        self,
        telemetry: object,
        *,
        prediction_psi: float | None = None,
        model_accuracy: float | None = None,
        model_balanced_accuracy: float | None = None,
        model_f1: float | None = None,
        model_log_loss: float | None = None,
        model_brier_score: float | None = None,
        calibration_error: float | None = None,
    ) -> tuple[Alert, ...]:
        """Record Phase-9 prediction telemetry in the common monitoring stream."""
        payload = prediction_payload(telemetry)
        timestamp = telemetry.timestamp
        symbol = telemetry.symbol
        correlation_id = f"{symbol}:{telemetry.model_version}:{telemetry.timestamp.isoformat()}"
        self.metrics.increment("model_predictions")

        event = self.emit(
            event_type="MODEL_PREDICTION",
            source="prediction_model",
            symbol=symbol,
            correlation_id=correlation_id,
            timestamp=timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp,
            payload=payload,
        )

        snapshot = MonitoringSnapshot(
            timestamp=timestamp.to_pydatetime() if hasattr(timestamp, "to_pydatetime") else timestamp,
            prediction_psi=prediction_psi,
            model_accuracy=model_accuracy,
            model_balanced_accuracy=model_balanced_accuracy,
            model_f1=model_f1,
            model_log_loss=model_log_loss,
            model_brier_score=model_brier_score,
            calibration_error=calibration_error,
        )
        return self.inspect_snapshot(
            snapshot,
            source="prediction_model",
            correlation_id=event.correlation_id,
        )

    def observe_model_metrics(
        self,
        *,
        timestamp: datetime,
        accuracy: float | None = None,
        balanced_accuracy: float | None = None,
        f1: float | None = None,
        log_loss: float | None = None,
        brier_score: float | None = None,
        calibration_error: float | None = None,
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Observe aggregate model-evaluation telemetry."""
        return self.inspect_snapshot(
            MonitoringSnapshot(
                timestamp=timestamp,
                model_accuracy=accuracy,
                model_balanced_accuracy=balanced_accuracy,
                model_f1=f1,
                model_log_loss=log_loss,
                model_brier_score=brier_score,
                calibration_error=calibration_error,
            ),
            source="model_evaluation",
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # M-5 STRATEGY
    # ------------------------------------------------------------------
    def observe_strategy_decision(
        self,
        decision: object,
        *,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record a Strategy/Journal decision snapshot, including NO_TRADE."""
        direction = str(decision.direction)
        direction = getattr(decision.direction, "value", direction)
        if direction == "NO_TRADE":
            self.metrics.increment("no_trade_decisions")
        else:
            self.metrics.increment("actionable_decisions")
        return self.emit(
            event_type="STRATEGY_DECISION",
            source="strategy_engine",
            symbol=decision.symbol,
            correlation_id=correlation_id or decision.trade_id,
            timestamp=decision.timestamp,
            payload=decision_payload(decision),
        )

    def performance(
        self,
        records: Iterable[object],
    ) -> PerformanceSnapshot:
        """Aggregate completed journal outcomes for M-5/M-8 reporting."""
        snapshot = performance_from_records(records)
        self.metrics.increment("performance_calculations")
        return snapshot

    def strategy_breakdown(
        self,
        records: Iterable[object],
    ) -> Mapping[str, float]:
        """Return net P&L grouped by any stable journal field."""
        return grouped_net_pnl(records, "direction")

    # ------------------------------------------------------------------
    # M-6 RISK
    # ------------------------------------------------------------------
    def observe_risk(
        self,
        *,
        timestamp: datetime,
        daily_pnl: float = 0.0,
        daily_loss_pct: float = 0.0,
        gross_exposure_pct: float = 0.0,
        open_positions: int = 0,
        entries_today: int = 0,
        risk_utilization_pct: float | None = None,
        kill_switch_active: bool = False,
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Observe risk utilization; Risk Engine remains authoritative."""
        self.metrics.increment("risk_observations")
        return self.inspect_snapshot(
            MonitoringSnapshot(
                timestamp=timestamp,
                daily_pnl=daily_pnl,
                daily_loss_pct=daily_loss_pct,
                gross_exposure_pct=gross_exposure_pct,
                open_positions=open_positions,
                entries_today=entries_today,
                risk_utilization_pct=risk_utilization_pct,
                kill_switch_active=kill_switch_active,
            ),
            source="risk_engine",
            correlation_id=correlation_id,
        )

    def observe_safety_decision(
        self,
        decision: object,
        *,
        timestamp: datetime | None = None,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record independent SafetyGate state without changing that decision."""
        if not decision.allowed:
            self.metrics.increment("safety_blocks")
        return self.emit(
            event_type="SAFETY_DECISION",
            source="independent_safety",
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            severity=(
                AlertSeverity.INFO
                if decision.allowed
                else AlertSeverity.CRITICAL
            ),
            payload=safety_payload(decision),
        )

    # ------------------------------------------------------------------
    # M-7 EXECUTION
    # ------------------------------------------------------------------
    def observe_execution(
        self,
        *,
        timestamp: datetime,
        orders_submitted: int = 0,
        orders_filled: int = 0,
        orders_rejected: int = 0,
        partial_fills: int = 0,
        execution_latency_ms: float | None = None,
        slippage_bps: float | None = None,
        reconciliation_mismatch: bool = False,
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Observe order lifecycle and reconciliation telemetry."""
        submitted = max(orders_submitted, 0)
        rejection_rate = (
            orders_rejected / submitted
            if submitted
            else None
        )
        snapshot = MonitoringSnapshot(
            timestamp=timestamp,
            orders_submitted=orders_submitted,
            orders_filled=orders_filled,
            orders_rejected=orders_rejected,
            partial_fill_count=partial_fills,
            execution_latency_ms=execution_latency_ms,
            slippage_bps=slippage_bps,
            order_rejection_rate=rejection_rate,
            reconciliation_mismatch=reconciliation_mismatch,
        )
        self.metrics.increment("orders_submitted", orders_submitted)
        self.metrics.increment("orders_filled", orders_filled)
        self.metrics.increment("orders_rejected", orders_rejected)
        self.metrics.increment("partial_fills", partial_fills)
        if execution_latency_ms is not None:
            self.metrics.observe("execution_latency_ms", execution_latency_ms)
        if slippage_bps is not None:
            self.metrics.observe("slippage_bps", slippage_bps)
        return self.inspect_snapshot(
            snapshot,
            source="execution_engine",
            correlation_id=correlation_id,
        )

    def observe_reconciliation(
        self,
        report: object,
        *,
        timestamp: datetime | None = None,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record authoritative local/broker reconciliation results."""
        if not report.safe:
            self.metrics.increment("reconciliation_mismatches")
        return self.emit(
            event_type="RECONCILIATION",
            source="reconciliation",
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            severity=(
                AlertSeverity.INFO
                if report.safe
                else AlertSeverity.EMERGENCY
            ),
            payload=reconciliation_payload(report),
        )

    # ------------------------------------------------------------------
    # M-8 OUTCOME / LEARNING
    # ------------------------------------------------------------------
    def observe_outcome(
        self,
        outcome: object,
        *,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record one completed journal outcome."""
        self.metrics.increment("completed_outcomes")
        return self.emit(
            event_type="TRADE_OUTCOME",
            source="trade_journal",
            symbol=outcome.symbol,
            correlation_id=correlation_id or outcome.trade_id,
            timestamp=outcome.exit_time,
            payload=outcome_payload(outcome),
        )

    def observe_learning(
        self,
        experiences: Iterable[object],
        *,
        timestamp: datetime | None = None,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record controlled Phase-18 learning evidence."""
        items = tuple(experiences)
        self.metrics.increment("learning_experiences", len(items))
        return self.emit(
            event_type="LEARNING_EVIDENCE",
            source="learning_engine",
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            payload={
                "experience_count": len(items),
            },
        )

    def observe_candidate_proposals(
        self,
        proposals: Iterable[object],
        *,
        timestamp: datetime | None = None,
        correlation_id: str | None = None,
    ) -> MonitoringEvent:
        """Record candidate-improvement proposals without promoting anything."""
        items = tuple(proposals)
        self.metrics.increment("candidate_proposals", len(items))
        return self.emit(
            event_type="CANDIDATE_PROPOSALS",
            source="candidate_improvement",
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=correlation_id,
            payload={"proposal_count": len(items)},
        )

    # ------------------------------------------------------------------
    # CORE SNAPSHOT / ALERTING
    # ------------------------------------------------------------------
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
        """Persist one immutable telemetry event."""
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
        self.metrics.increment("monitoring_events")
        return event

    def inspect_snapshot(
        self,
        snapshot: MonitoringSnapshot,
        *,
        source: str = "monitoring_engine",
        correlation_id: str | None = None,
    ) -> tuple[Alert, ...]:
        """Evaluate a cross-domain snapshot against observational thresholds."""
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
            alert = self._alert(
                timestamp=snapshot.timestamp,
                severity=severity,
                code=code,
                source=source,
                message=message,
                correlation_id=correlation_id,
                details=details,
            )
            if alert is not None:
                alerts.append(alert)

        # M-1
        check(
            snapshot.system_health is ComponentHealth.FAILED,
            severity=AlertSeverity.EMERGENCY,
            code="SYSTEM_HEALTH_FAILED",
            message="One or more critical STOCK_BOT components have failed.",
            details={"system_health": snapshot.system_health.value},
        )
        if snapshot.heartbeat_age_seconds is not None:
            check(
                snapshot.heartbeat_age_seconds > 30.0,
                severity=AlertSeverity.CRITICAL,
                code="HEARTBEAT_STALE",
                message="Monitoring heartbeat age exceeded the operational threshold.",
                details={"age_seconds": snapshot.heartbeat_age_seconds},
            )

        # M-2
        if snapshot.data_freshness_seconds is not None:
            check(
                snapshot.data_freshness_seconds > self.policy.max_data_freshness_seconds,
                severity=AlertSeverity.CRITICAL,
                code="DATA_STALE",
                message="Market data freshness exceeded monitoring threshold.",
                details={
                    "value_seconds": snapshot.data_freshness_seconds,
                    "threshold_seconds": self.policy.max_data_freshness_seconds,
                },
            )
        for field_name, code, message in (
            ("missing_candles", "MISSING_CANDLES", "Missing market candles detected."),
            ("duplicate_events", "DUPLICATE_EVENTS", "Duplicate market events detected."),
            ("invalid_ohlc_count", "INVALID_OHLC", "Invalid OHLC observations detected."),
            ("connection_failures", "MARKET_CONNECTION_FAILURE", "Market feed connection failures detected."),
        ):
            check(
                getattr(snapshot, field_name) > 0,
                severity=AlertSeverity.CRITICAL,
                code=code,
                message=message,
                details={"count": getattr(snapshot, field_name)},
            )
        if snapshot.feed_latency_ms is not None:
            check(
                snapshot.feed_latency_ms > self.policy.max_feed_latency_ms,
                severity=AlertSeverity.WARNING,
                code="FEED_LATENCY_HIGH",
                message="Market-feed latency exceeded threshold.",
                details={
                    "value_ms": snapshot.feed_latency_ms,
                    "threshold_ms": self.policy.max_feed_latency_ms,
                },
            )
        if snapshot.clock_drift_ms is not None:
            check(
                snapshot.clock_drift_ms > self.policy.max_clock_drift_ms,
                severity=AlertSeverity.WARNING,
                code="CLOCK_DRIFT_HIGH",
                message="Market clock drift exceeded threshold.",
                details={
                    "value_ms": snapshot.clock_drift_ms,
                    "threshold_ms": self.policy.max_clock_drift_ms,
                },
            )

        # M-3
        if snapshot.feature_missing_rate is not None:
            check(
                snapshot.feature_missing_rate > self.policy.max_feature_missing_rate,
                severity=AlertSeverity.CRITICAL,
                code="FEATURE_MISSING_RATE_HIGH",
                message="Feature missing-rate exceeded threshold.",
                details={
                    "value": snapshot.feature_missing_rate,
                    "threshold": self.policy.max_feature_missing_rate,
                },
            )
        if snapshot.feature_inf_rate is not None:
            check(
                snapshot.feature_inf_rate > self.policy.max_feature_inf_rate,
                severity=AlertSeverity.CRITICAL,
                code="FEATURE_INFINITY_RATE_HIGH",
                message="Feature infinity-rate exceeded threshold.",
                details={
                    "value": snapshot.feature_inf_rate,
                    "threshold": self.policy.max_feature_inf_rate,
                },
            )
        if snapshot.feature_stale_rate is not None:
            check(
                snapshot.feature_stale_rate > self.policy.max_stale_rate,
                severity=AlertSeverity.WARNING,
                code="FEATURE_STALE_RATE_HIGH",
                message="Feature stale-rate exceeded threshold.",
                details={
                    "value": snapshot.feature_stale_rate,
                    "threshold": self.policy.max_stale_rate,
                },
            )
        check(
            snapshot.feature_drift_count > 0,
            severity=AlertSeverity.WARNING,
            code="FEATURE_DRIFT_DETECTED",
            message="One or more feature distributions exceeded drift thresholds.",
            details={"count": snapshot.feature_drift_count},
        )

        # M-4
        for field_name, code, message in (
            ("error_rate", "MODEL_ERROR_RATE_HIGH", "Model/inference operational error-rate exceeded threshold."),
            ("stale_rate", "MODEL_STALE_RATE_HIGH", "Model telemetry stale-rate exceeded threshold."),
        ):
            value = getattr(snapshot, field_name)
            if value is not None:
                check(
                    value > (
                        self.policy.max_error_rate
                        if field_name == "error_rate"
                        else self.policy.max_stale_rate
                    ),
                    severity=AlertSeverity.CRITICAL,
                    code=code,
                    message=message,
                    details={
                        "value": value,
                        "threshold": (
                            self.policy.max_error_rate
                            if field_name == "error_rate"
                            else self.policy.max_stale_rate
                        ),
                    },
                )
        if snapshot.prediction_psi is not None:
            check(
                snapshot.prediction_psi > self.policy.max_prediction_psi,
                severity=AlertSeverity.WARNING,
                code="PREDICTION_DRIFT",
                message="Prediction distribution drift exceeded threshold.",
                details={
                    "psi": snapshot.prediction_psi,
                    "threshold": self.policy.max_prediction_psi,
                },
            )
        if snapshot.model_accuracy is not None and self.policy.min_model_accuracy > 0:
            check(
                snapshot.model_accuracy < self.policy.min_model_accuracy,
                severity=AlertSeverity.WARNING,
                code="MODEL_ACCURACY_LOW",
                message="Observed model accuracy is below monitoring floor.",
                details={
                    "value": snapshot.model_accuracy,
                    "threshold": self.policy.min_model_accuracy,
                },
            )
        if snapshot.model_log_loss is not None:
            check(
                snapshot.model_log_loss > self.policy.max_model_log_loss,
                severity=AlertSeverity.WARNING,
                code="MODEL_LOG_LOSS_HIGH",
                message="Observed model log loss exceeded monitoring threshold.",
                details={
                    "value": snapshot.model_log_loss,
                    "threshold": self.policy.max_model_log_loss,
                },
            )
        if snapshot.calibration_error is not None:
            check(
                snapshot.calibration_error > self.policy.max_calibration_error,
                severity=AlertSeverity.WARNING,
                code="MODEL_CALIBRATION_DEGRADED",
                message="Model calibration error exceeded monitoring threshold.",
                details={
                    "value": snapshot.calibration_error,
                    "threshold": self.policy.max_calibration_error,
                },
            )

        # M-5
        check(
            snapshot.drawdown_pct if hasattr(snapshot, "drawdown_pct") else snapshot.max_drawdown_pct
            > self.policy.max_drawdown_pct,
            severity=AlertSeverity.CRITICAL,
            code="DRAWDOWN_HIGH",
            message="Observed drawdown exceeded monitoring threshold.",
            details={
                "value_pct": snapshot.max_drawdown_pct,
                "threshold_pct": self.policy.max_drawdown_pct,
            },
        )
        if snapshot.win_rate is not None and self.policy.min_win_rate > 0:
            check(
                snapshot.win_rate < self.policy.min_win_rate,
                severity=AlertSeverity.WARNING,
                code="WIN_RATE_LOW",
                message="Observed strategy win-rate is below monitoring floor.",
                details={"value": snapshot.win_rate, "threshold": self.policy.min_win_rate},
            )
        if snapshot.expectancy is not None and self.policy.min_expectancy is not None:
            check(
                snapshot.expectancy < self.policy.min_expectancy,
                severity=AlertSeverity.WARNING,
                code="EXPECTANCY_LOW",
                message="Observed strategy expectancy is below monitoring floor.",
                details={"value": snapshot.expectancy, "threshold": self.policy.min_expectancy},
            )

        # M-6
        check(
            snapshot.daily_loss_pct > self.policy.max_daily_loss_pct,
            severity=AlertSeverity.EMERGENCY,
            code="DAILY_LOSS_LIMIT_BREACH",
            message="Observed daily loss exceeded the frozen paper-trading limit.",
            details={
                "value_pct": snapshot.daily_loss_pct,
                "threshold_pct": self.policy.max_daily_loss_pct,
            },
        )
        check(
            snapshot.gross_exposure_pct > self.policy.max_gross_exposure_pct,
            severity=AlertSeverity.CRITICAL,
            code="GROSS_EXPOSURE_HIGH",
            message="Observed gross exposure exceeded monitoring threshold.",
            details={
                "value_pct": snapshot.gross_exposure_pct,
                "threshold_pct": self.policy.max_gross_exposure_pct,
            },
        )
        check(
            snapshot.open_positions > self.policy.max_open_positions,
            severity=AlertSeverity.EMERGENCY,
            code="OPEN_POSITION_LIMIT_BREACH",
            message="Observed open positions exceed monitoring limit.",
            details={
                "value": snapshot.open_positions,
                "threshold": self.policy.max_open_positions,
            },
        )
        check(
            snapshot.entries_today > self.policy.max_entries_today,
            severity=AlertSeverity.EMERGENCY,
            code="ENTRY_LIMIT_BREACH",
            message="Observed daily entries exceed monitoring limit.",
            details={
                "value": snapshot.entries_today,
                "threshold": self.policy.max_entries_today,
            },
        )
        check(
            snapshot.kill_switch_active,
            severity=AlertSeverity.EMERGENCY,
            code="KILL_SWITCH_ACTIVE",
            message="Independent kill switch is active.",
            details={},
        )

        # M-7
        if snapshot.execution_latency_ms is not None:
            check(
                snapshot.execution_latency_ms > self.policy.max_execution_latency_ms,
                severity=AlertSeverity.WARNING,
                code="EXECUTION_LATENCY_HIGH",
                message="Execution latency exceeded monitoring threshold.",
                details={
                    "value_ms": snapshot.execution_latency_ms,
                    "threshold_ms": self.policy.max_execution_latency_ms,
                },
            )
        if snapshot.slippage_bps is not None:
            check(
                snapshot.slippage_bps > self.policy.max_slippage_bps,
                severity=AlertSeverity.WARNING,
                code="SLIPPAGE_HIGH",
                message="Observed slippage exceeded monitoring threshold.",
                details={
                    "value_bps": snapshot.slippage_bps,
                    "threshold_bps": self.policy.max_slippage_bps,
                },
            )
        if snapshot.order_rejection_rate is not None:
            check(
                snapshot.order_rejection_rate > self.policy.max_order_rejection_rate,
                severity=AlertSeverity.CRITICAL,
                code="ORDER_REJECTION_RATE_HIGH",
                message="Order rejection rate exceeded monitoring threshold.",
                details={
                    "value": snapshot.order_rejection_rate,
                    "threshold": self.policy.max_order_rejection_rate,
                },
            )
        check(
            snapshot.reconciliation_mismatch,
            severity=AlertSeverity.EMERGENCY,
            code="POSITION_RECONCILIATION_MISMATCH",
            message="Local and authoritative position state does not reconcile.",
            details={},
        )

        self.emit(
            event_type="MONITORING_SNAPSHOT",
            source=source,
            correlation_id=correlation_id,
            timestamp=snapshot.timestamp,
            payload={
                "snapshot": snapshot.to_dict(),
                "alert_codes": [alert.code for alert in alerts],
                "total_pnl": snapshot.total_pnl,
            },
        )
        return tuple(alerts)

    def report(
        self,
        snapshot: MonitoringSnapshot,
        *,
        health: SystemHealth | None = None,
        drift: Iterable[DriftReport] = (),
        correlation_id: str | None = None,
    ) -> MonitoringReport:
        """Build the dashboard-ready report for one monitoring point."""
        resolved_health = health or self.build_health(timestamp=snapshot.timestamp)
        alerts = self.inspect_snapshot(
            snapshot,
            source="monitoring_report",
            correlation_id=correlation_id,
        )
        return build_trade_report(
            snapshot=snapshot,
            health=resolved_health,
            alerts=alerts,
            drift=tuple(drift),
        )

    def class_distribution(self, predictions: Iterable[str]) -> Mapping[str, int]:
        """Return observed model prediction class counts."""
        return dict(Counter(predictions))

    def alerts(self) -> tuple[Alert, ...]:
        """Return persisted alerts."""
        return self.store.read_alerts()

    def events(self) -> tuple[MonitoringEvent, ...]:
        """Return persisted telemetry."""
        return self.store.read_events()

    def metrics_snapshot(self) -> Mapping[str, object]:
        """Return process-local metric state."""
        return self.metrics.snapshot()

    def _alert(
        self,
        *,
        timestamp: datetime,
        severity: AlertSeverity,
        code: str,
        source: str,
        message: str,
        correlation_id: str | None,
        details: Mapping,
    ) -> Alert | None:
        """Create, persist and optionally route one alert with deduplication."""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            timestamp=timestamp,
            severity=severity,
            code=code,
            source=source,
            message=message,
            correlation_id=correlation_id,
            details=dict(details),
        )
        self.store.append_alert(alert)
        self.metrics.increment("alerts_generated")
        self.alert_manager.route(alert)
        return alert
