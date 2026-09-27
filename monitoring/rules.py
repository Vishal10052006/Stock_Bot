"""Configurable monitoring thresholds for STOCK_BOT.

These values are observation policies. They do not replace or modify the
authoritative Strategy, Risk, Safety, or Execution contracts.

References:
    TRADING_SPECIFICATION.md.
    docs/PHASE_23_MONITORING.md.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Operational thresholds for M-1 through M-8."""

    # M-1
    max_heartbeat_age_seconds: float = 30.0

    # M-2
    max_data_freshness_seconds: float = 15.0
    max_feed_latency_ms: float = 1000.0
    max_clock_drift_ms: float = 1000.0

    # M-3
    max_feature_missing_rate: float = 0.01
    max_feature_inf_rate: float = 0.0
    max_feature_stale_rate: float = 0.10

    # M-4
    max_error_rate: float = 0.05
    max_stale_rate: float = 0.10
    max_prediction_psi: float = 0.20
    min_model_accuracy: float = 0.0
    max_model_log_loss: float = 1.5
    max_calibration_error: float = 0.20

    # M-5
    min_win_rate: float = 0.0
    min_expectancy: float | None = None
    max_drawdown_pct: float = 1.5

    # M-6 — mirrors the frozen paper configuration for observation only.
    max_daily_loss_pct: float = 1.5
    max_gross_exposure_pct: float = 75.0
    max_open_positions: int = 3
    max_entries_today: int = 5

    # M-7
    max_execution_latency_ms: float = 2000.0
    max_slippage_bps: float = 50.0
    max_order_rejection_rate: float = 0.05

    def __post_init__(self) -> None:
        bounded = (
            ("max_error_rate", self.max_error_rate),
            ("max_stale_rate", self.max_stale_rate),
            ("max_feature_missing_rate", self.max_feature_missing_rate),
            ("max_feature_inf_rate", self.max_feature_inf_rate),
            ("max_feature_stale_rate", self.max_feature_stale_rate),
            ("max_calibration_error", self.max_calibration_error),
            ("min_model_accuracy", self.min_model_accuracy),
            ("min_win_rate", self.min_win_rate),
            ("max_order_rejection_rate", self.max_order_rejection_rate),
        )
        for name, value in bounded:
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        non_negative = (
            ("max_heartbeat_age_seconds", self.max_heartbeat_age_seconds),
            ("max_data_freshness_seconds", self.max_data_freshness_seconds),
            ("max_feed_latency_ms", self.max_feed_latency_ms),
            ("max_clock_drift_ms", self.max_clock_drift_ms),
            ("max_prediction_psi", self.max_prediction_psi),
            ("max_model_log_loss", self.max_model_log_loss),
            ("max_drawdown_pct", self.max_drawdown_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
            ("max_gross_exposure_pct", self.max_gross_exposure_pct),
            ("max_execution_latency_ms", self.max_execution_latency_ms),
            ("max_slippage_bps", self.max_slippage_bps),
        )
        for name, value in non_negative:
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

        if self.min_expectancy is not None and not isinstance(self.min_expectancy, (int, float)):
            raise TypeError("min_expectancy must be numeric or None")
        if self.max_open_positions < 0 or self.max_entries_today < 0:
            raise ValueError("position/entry limits must be non-negative")
