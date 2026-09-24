"""Pure monitoring evaluation functions.

No function in this module has trading authority.

References:
    docs/MONITORING_ENGINE.md
    docs/PHASE_9_SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .alerts import Alert, AlertEngine, AlertSeverity
from .drift import population_stability_index
from .metrics import MetricsSnapshot
from .policy import MonitoringPolicy


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Immutable distribution-drift measurements."""

    prediction_psi: float | None = None
    feature_psi: tuple[tuple[str, float], ...] = ()
    regime_psi: float | None = None

    @property
    def max_feature_psi(self) -> float | None:
        """Return the maximum feature PSI."""
        if not self.feature_psi:
            return None
        return max(value for _, value in self.feature_psi)


@dataclass(frozen=True, slots=True)
class MonitoringEvaluation:
    """Immutable monitoring result, never a trading decision."""

    healthy: bool
    alerts: tuple[Alert, ...]
    drift: DriftReport
    summary: dict[str, float | int | bool | None]


def evaluate_monitoring(
    snapshot: MetricsSnapshot,
    *,
    policy: MonitoringPolicy | None = None,
    reference_prediction_probabilities: Sequence[float] = (),
    reference_features: dict[str, Sequence[float]] | None = None,
    current_features: dict[str, Sequence[float]] | None = None,
    reference_regimes: Sequence[float] = (),
    current_regimes: Sequence[float] = (),
    alert_engine: AlertEngine | None = None,
) -> MonitoringEvaluation:
    """Evaluate current telemetry against operational policy."""
    if not isinstance(snapshot, MetricsSnapshot):
        raise TypeError("snapshot must be a MetricsSnapshot")

    policy = policy or MonitoringPolicy()
    engine = alert_engine or AlertEngine()

    prediction_psi = None
    if reference_prediction_probabilities and snapshot.model.long_probabilities:
        prediction_psi = population_stability_index(
            reference_prediction_probabilities,
            snapshot.model.long_probabilities,
        )

    feature_psis: dict[str, float] = {}
    if reference_features is not None and current_features is not None:
        for name in sorted(set(reference_features) & set(current_features)):
            reference = reference_features[name]
            current = current_features[name]
            if reference and current:
                feature_psis[name] = population_stability_index(
                    reference,
                    current,
                )

    regime_psi = None
    if reference_regimes and current_regimes:
        regime_psi = population_stability_index(
            reference_regimes,
            current_regimes,
        )

    alerts: list[Alert] = []

    def add(
        code: str,
        severity: AlertSeverity,
        message: str,
        value: float | None = None,
        threshold: float | None = None,
    ) -> None:
        """Register an alert using a stable condition fingerprint."""
        fingerprint = f"{code}:{value}:{threshold}"
        alert = engine.emit(
            code=code,
            severity=severity,
            message=message,
            source="monitoring.evaluator",
            fingerprint=fingerprint,
            value=value,
            threshold=threshold,
        )
        if alert is not None:
            alerts.append(alert)

    if snapshot.system.error_rate > policy.max_event_error_rate:
        add(
            "SYSTEM_ERROR_RATE_EXCEEDED",
            AlertSeverity.CRITICAL,
            "System event error rate exceeded monitoring policy.",
            snapshot.system.error_rate,
            policy.max_event_error_rate,
        )

    if (
        snapshot.system.latency_p95_ms is not None
        and snapshot.system.latency_p95_ms > policy.max_data_latency_ms
    ):
        add(
            "SYSTEM_LATENCY_EXCEEDED",
            AlertSeverity.WARNING,
            "System telemetry latency exceeded monitoring policy.",
            snapshot.system.latency_p95_ms,
            policy.max_data_latency_ms,
        )

    if prediction_psi is not None and prediction_psi > policy.max_prediction_psi:
        add(
            "PREDICTION_DRIFT_EXCEEDED",
            AlertSeverity.WARNING,
            "Prediction probability drift exceeded monitoring policy.",
            prediction_psi,
            policy.max_prediction_psi,
        )

    max_feature_psi = max(feature_psis.values(), default=None)
    if (
        max_feature_psi is not None
        and max_feature_psi > policy.max_feature_drift_psi
    ):
        add(
            "FEATURE_DRIFT_EXCEEDED",
            AlertSeverity.WARNING,
            "At least one feature distribution exceeded drift policy.",
            max_feature_psi,
            policy.max_feature_drift_psi,
        )

    if regime_psi is not None and regime_psi > policy.max_regime_drift_psi:
        add(
            "REGIME_DRIFT_EXCEEDED",
            AlertSeverity.WARNING,
            "Market regime distribution drift exceeded monitoring policy.",
            regime_psi,
            policy.max_regime_drift_psi,
        )

    if snapshot.execution.rejection_rate > policy.max_execution_error_rate:
        add(
            "EXECUTION_REJECTION_RATE_EXCEEDED",
            AlertSeverity.CRITICAL,
            "Execution rejection rate exceeded monitoring policy.",
            snapshot.execution.rejection_rate,
            policy.max_execution_error_rate,
        )

    slippage = snapshot.execution.mean_slippage_bps
    if (
        slippage is not None
        and slippage > policy.max_execution_slippage_bps
    ):
        add(
            "EXECUTION_SLIPPAGE_EXCEEDED",
            AlertSeverity.WARNING,
            "Mean execution slippage exceeded monitoring policy.",
            slippage,
            policy.max_execution_slippage_bps,
        )

    if snapshot.execution.reconciliation_mismatches > 0:
        add(
            "RECONCILIATION_MISMATCH",
            AlertSeverity.CRITICAL,
            "Execution reconciliation reported a position/state mismatch.",
            float(snapshot.execution.reconciliation_mismatches),
            0.0,
        )

    if snapshot.risk.kill_switch_active:
        add(
            "KILL_SWITCH_ACTIVE",
            AlertSeverity.EMERGENCY,
            "Independent safety state reports the kill switch as active.",
        )

    if snapshot.risk.daily_loss_fraction >= policy.daily_loss_limit_fraction:
        add(
            "DAILY_LOSS_LIMIT_REACHED",
            AlertSeverity.EMERGENCY,
            "Observed daily loss reached the configured project limit.",
            snapshot.risk.daily_loss_fraction,
            policy.daily_loss_limit_fraction,
        )

    calibration = snapshot.model.mean_log_loss
    if (
        calibration is not None
        and calibration > policy.max_calibration_log_loss
    ):
        add(
            "MODEL_CALIBRATION_DEGRADED",
            AlertSeverity.WARNING,
            "Observed mean log loss exceeded monitoring policy.",
            calibration,
            policy.max_calibration_log_loss,
        )

    summary: dict[str, float | int | bool | None] = {
        "system_error_rate": snapshot.system.error_rate,
        "system_latency_p95_ms": snapshot.system.latency_p95_ms,
        "prediction_psi": prediction_psi,
        "max_feature_psi": max_feature_psi,
        "regime_psi": regime_psi,
        "model_accuracy": snapshot.model.accuracy,
        "model_log_loss": snapshot.model.mean_log_loss,
        "strategy_trade_count": snapshot.strategy.trade_count,
        "strategy_no_trade_rate": snapshot.strategy.no_trade_rate,
        "strategy_win_rate": snapshot.strategy.win_rate,
        "strategy_average_r": snapshot.strategy.average_r,
        "equity": snapshot.risk.equity,
        "daily_pnl": snapshot.risk.daily_pnl,
        "drawdown": snapshot.risk.drawdown,
        "gross_exposure": snapshot.risk.gross_exposure,
        "execution_fill_rate": snapshot.execution.fill_rate,
        "execution_rejection_rate": snapshot.execution.rejection_rate,
        "mean_slippage_bps": snapshot.execution.mean_slippage_bps,
        "reconciliation_mismatches": snapshot.execution.reconciliation_mismatches,
        "kill_switch_active": snapshot.risk.kill_switch_active,
        "healthy": not alerts,
    }

    return MonitoringEvaluation(
        healthy=not alerts,
        alerts=tuple(alerts),
        drift=DriftReport(
            prediction_psi=prediction_psi,
            feature_psi=tuple(sorted(feature_psis.items())),
            regime_psi=regime_psi,
        ),
        summary=summary,
    )
