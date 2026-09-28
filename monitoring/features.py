from __future__ import annotations

from dataclasses import dataclass
import math

from .drift import DriftReport, calculate_psi


@dataclass(frozen=True, slots=True)
class FeatureMonitoringSnapshot:
    """Feature quality and distribution telemetry for one window."""

    feature_count: int
    invalid_count: int = 0
    missing_count: int = 0
    reference_values: tuple[float, ...] = ()
    current_values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.feature_count < 0:
            raise ValueError("feature_count must be non-negative")
        if self.invalid_count < 0 or self.missing_count < 0:
            raise ValueError("feature quality counters must be non-negative")
        if self.invalid_count > self.feature_count:
            raise ValueError("invalid_count cannot exceed feature_count")
        if self.missing_count > self.feature_count:
            raise ValueError("missing_count cannot exceed feature_count")
        for value in (*self.reference_values, *self.current_values):
            if not math.isfinite(float(value)):
                raise ValueError("feature values must be finite")


def evaluate_feature_monitoring(
    snapshot: FeatureMonitoringSnapshot,
    *,
    max_psi: float = 0.20,
    warning_psi: float | None = 0.10,
) -> tuple[dict[str, float | int], tuple[DriftReport, ...], tuple[str, ...]]:
    """Evaluate feature quality and distribution drift without mutation."""
    if max_psi < 0:
        raise ValueError("max_psi must be non-negative")
    if warning_psi is not None and (
        warning_psi < 0 or warning_psi > max_psi
    ):
        raise ValueError("warning_psi must be between zero and max_psi")

    denominator = max(snapshot.feature_count, 1)
    metrics: dict[str, float | int] = {
        "feature_count": snapshot.feature_count,
        "invalid_count": snapshot.invalid_count,
        "missing_count": snapshot.missing_count,
        "invalid_rate": snapshot.invalid_count / denominator,
        "missing_rate": snapshot.missing_count / denominator,
    }
    reports: list[DriftReport] = []
    alerts: list[str] = []

    if snapshot.reference_values and snapshot.current_values:
        psi = calculate_psi(
            list(snapshot.reference_values),
            list(snapshot.current_values),
        )
        status = (
            "CRITICAL"
            if psi > max_psi
            else "WARNING"
            if warning_psi is not None and psi > warning_psi
            else "OK"
        )
        reports.append(
            DriftReport(
                "feature_distribution",
                psi,
                len(snapshot.reference_values),
                len(snapshot.current_values),
                status,
            )
        )
        metrics["feature_psi"] = psi
        if status == "CRITICAL":
            alerts.append("FEATURE_DRIFT_EXCEEDED")
        elif status == "WARNING":
            alerts.append("FEATURE_DRIFT_WARNING")

    return metrics, tuple(reports), tuple(alerts)
