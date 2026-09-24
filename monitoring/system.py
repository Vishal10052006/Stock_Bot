from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class SystemMonitoringSnapshot:
    """Operational/data-quality telemetry for one monitoring window.

    This is observational only. It does not authorize, block, or mutate
    trading, execution, risk, or model state.
    """

    total_events: int
    failed_events: int = 0
    stale_events: int = 0
    duplicate_events: int = 0
    invalid_events: int = 0
    missing_data_gaps: int = 0
    latency_avg_ms: float | None = None
    latency_p95_ms: float | None = None

    def __post_init__(self) -> None:
        if self.total_events < 0:
            raise ValueError("total_events must be non-negative")
        counters = (
            self.failed_events,
            self.stale_events,
            self.duplicate_events,
            self.invalid_events,
            self.missing_data_gaps,
        )
        if any(value < 0 for value in counters):
            raise ValueError("system counters must be non-negative")
        if any(value > self.total_events for value in counters[:4]):
            raise ValueError("event counters cannot exceed total_events")
        for value in (self.latency_avg_ms, self.latency_p95_ms):
            if value is not None and (
                not math.isfinite(float(value)) or float(value) < 0
            ):
                raise ValueError("latency metrics must be finite and non-negative")


def evaluate_system_monitoring(
    snapshot: SystemMonitoringSnapshot,
    *,
    max_error_rate: float = 0.05,
    max_stale_rate: float = 0.10,
) -> tuple[dict[str, float | int | None], tuple[str, ...]]:
    """Evaluate operational/data-quality telemetry without control authority."""
    if not 0 <= max_error_rate <= 1:
        raise ValueError("max_error_rate must be in [0, 1]")
    if not 0 <= max_stale_rate <= 1:
        raise ValueError("max_stale_rate must be in [0, 1]")

    denominator = max(snapshot.total_events, 1)
    error_rate = snapshot.failed_events / denominator
    stale_rate = snapshot.stale_events / denominator

    metrics: dict[str, float | int | None] = {
        "total_events": snapshot.total_events,
        "failed_events": snapshot.failed_events,
        "stale_events": snapshot.stale_events,
        "duplicate_events": snapshot.duplicate_events,
        "invalid_events": snapshot.invalid_events,
        "missing_data_gaps": snapshot.missing_data_gaps,
        "error_rate": error_rate,
        "stale_rate": stale_rate,
        "latency_avg_ms": snapshot.latency_avg_ms,
        "latency_p95_ms": snapshot.latency_p95_ms,
    }
    alerts: list[str] = []
    if error_rate > max_error_rate:
        alerts.append("ERROR_RATE_EXCEEDED")
    if stale_rate > max_stale_rate:
        alerts.append("STALE_RATE_EXCEEDED")
    return metrics, tuple(alerts)
