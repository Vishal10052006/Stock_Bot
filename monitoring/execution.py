"""Execution telemetry contracts for the observational Monitoring Engine."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ExecutionMonitoringSnapshot:
    """Aggregate execution observations; never grants execution authority."""

    order_count: int
    filled_count: int
    rejected_count: int = 0
    partial_fill_count: int = 0
    total_latency_seconds: float = 0.0
    total_slippage: float = 0.0

    def __post_init__(self) -> None:
        if self.order_count < 0:
            raise ValueError("order_count must be non-negative")
        for name in ("filled_count", "rejected_count", "partial_fill_count"):
            value = int(getattr(self, name))
            if value < 0 or value > self.order_count:
                raise ValueError(f"{name} must be within order_count")
        if self.filled_count + self.rejected_count > self.order_count:
            raise ValueError("filled_count + rejected_count cannot exceed order_count")
        if self.partial_fill_count > self.filled_count:
            raise ValueError("partial_fill_count cannot exceed filled_count")
        for name in ("total_latency_seconds", "total_slippage"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be non-negative finite")


def evaluate_execution_monitoring(
    snapshot: ExecutionMonitoringSnapshot,
    *,
    max_rejection_rate: float = 0.10,
) -> tuple[dict[str, float | int], tuple[str, ...]]:
    """Return execution-quality metrics and observational alerts."""
    if not 0.0 <= max_rejection_rate <= 1.0:
        raise ValueError("max_rejection_rate must be between 0 and 1")
    if snapshot.order_count == 0:
        return (
            {
                "order_count": 0,
                "fill_rate": 0.0,
                "rejection_rate": 0.0,
                "partial_fill_rate": 0.0,
                "average_latency_seconds": 0.0,
                "average_slippage": 0.0,
            },
            (),
        )

    n = snapshot.order_count
    metrics = {
        "order_count": n,
        "fill_rate": snapshot.filled_count / n,
        "rejection_rate": snapshot.rejected_count / n,
        "partial_fill_rate": snapshot.partial_fill_count / n,
        "average_latency_seconds": snapshot.total_latency_seconds / n,
        "average_slippage": snapshot.total_slippage / n,
    }
    alerts = (
        ("EXECUTION_REJECTION_RATE_HIGH",)
        if metrics["rejection_rate"] > max_rejection_rate
        else ()
    )
    return metrics, alerts
