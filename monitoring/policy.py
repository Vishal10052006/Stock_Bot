"""Monitoring thresholds and policy contracts.

References:
    docs/MONITORING_ENGINE.md
    TRADING_SPECIFICATION.md
"""


from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Validated thresholds used by the monitoring evaluator."""

    max_event_error_rate: float = 0.05
    max_stale_rate: float = 0.10
    max_prediction_psi: float = 0.20
    max_feature_drift_psi: float = 0.20
    max_regime_drift_psi: float = 0.20
    max_execution_error_rate: float = 0.05
    max_execution_slippage_bps: float = 25.0
    max_data_latency_ms: float = 2_000.0
    max_calibration_log_loss: float = 1.50
    daily_loss_limit_fraction: float = 0.015

    def __post_init__(self) -> None:
        """Reject invalid thresholds early."""
        bounded = (
            "max_event_error_rate",
            "max_stale_rate",
            "max_execution_error_rate",
            "daily_loss_limit_fraction",
        )
        for name in bounded:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")

        non_negative = (
            "max_prediction_psi",
            "max_feature_drift_psi",
            "max_regime_drift_psi",
            "max_execution_slippage_bps",
            "max_data_latency_ms",
            "max_calibration_log_loss",
        )
        for name in non_negative:
            if float(getattr(self, name)) < 0.0:
                raise ValueError(f"{name} must be non-negative")
