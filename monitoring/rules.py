"""Configurable monitoring thresholds for STOCK_BOT.

Thresholds are observational defaults. They do not replace or modify the
frozen Risk Engine limits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Operational monitoring thresholds."""

    max_data_freshness_seconds: float = 15.0
    max_feed_latency_ms: float = 1000.0
    max_error_rate: float = 0.05
    max_stale_rate: float = 0.10
    max_feature_missing_rate: float = 0.01
    max_feature_inf_rate: float = 0.0
    max_prediction_psi: float = 0.20
    min_model_accuracy: float = 0.0
    max_model_log_loss: float = 1.5
    max_drawdown_pct: float = 1.5
    max_gross_exposure_pct: float = 75.0
    max_open_positions: int = 3
    max_entries_today: int = 5
    max_execution_latency_ms: float = 2000.0
    max_slippage_bps: float = 50.0
    max_order_rejection_rate: float = 0.05

    def __post_init__(self) -> None:
        bounded = (
            ("error_rate", self.max_error_rate),
            ("stale_rate", self.max_stale_rate),
            ("feature_missing_rate", self.max_feature_missing_rate),
            ("feature_inf_rate", self.max_feature_inf_rate),
            ("prediction_psi", self.max_prediction_psi),
            ("order_rejection_rate", self.max_order_rejection_rate),
        )
        for name, value in bounded:
            if value < 0 or value > 1 and name != "prediction_psi":
                raise ValueError(f"{name} must be between 0 and 1")
        if self.max_prediction_psi < 0:
            raise ValueError("max_prediction_psi must be non-negative")
        if self.min_model_accuracy < 0 or self.min_model_accuracy > 1:
            raise ValueError("min_model_accuracy must be between 0 and 1")
        if self.max_model_log_loss < 0:
            raise ValueError("max_model_log_loss must be non-negative")
        if self.max_drawdown_pct < 0 or self.max_gross_exposure_pct < 0:
            raise ValueError("risk percentages must be non-negative")
        if self.max_open_positions < 0 or self.max_entries_today < 0:
            raise ValueError("position/entry limits must be non-negative")
        if self.max_data_freshness_seconds < 0 or self.max_feed_latency_ms < 0:
            raise ValueError("latency thresholds must be non-negative")
        if self.max_execution_latency_ms < 0 or self.max_slippage_bps < 0:
            raise ValueError("execution thresholds must be non-negative")
