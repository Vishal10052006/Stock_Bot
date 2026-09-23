"""S26 experiment and prediction monitoring boundary."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math

from research.monitoring.drift import population_stability_index


@dataclass(frozen=True, slots=True)
class MonitoringPolicy:
    """Thresholds for operational monitoring alerts."""

    max_error_rate: float = 0.05
    max_stale_rate: float = 0.10
    max_prediction_psi: float = 0.20

    def __post_init__(self) -> None:
        if not 0 <= self.max_error_rate <= 1:
            raise ValueError("max_error_rate must be in [0, 1]")
        if not 0 <= self.max_stale_rate <= 1:
            raise ValueError("max_stale_rate must be in [0, 1]")
        if self.max_prediction_psi < 0:
            raise ValueError("max_prediction_psi must be non-negative")


@dataclass(frozen=True, slots=True)
class MonitoringSnapshot:
    """Immutable point-in-time monitoring measurement."""

    total_events: int
    failed_events: int
    stale_events: int
    reference_probabilities: tuple[float, ...] = ()
    current_probabilities: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.total_events < 0:
            raise ValueError("total_events must be non-negative")
        if self.failed_events < 0 or self.stale_events < 0:
            raise ValueError("event counters must be non-negative")
        if self.failed_events > self.total_events:
            raise ValueError("failed_events cannot exceed total_events")
        if self.stale_events > self.total_events:
            raise ValueError("stale_events cannot exceed total_events")
        for value in (
            *self.reference_probabilities,
            *self.current_probabilities,
        ):
            if not math.isfinite(float(value)):
                raise ValueError("monitoring probabilities must be finite")


@dataclass(frozen=True, slots=True)
class MonitoringReport:
    """Immutable monitoring result with explicit alerts."""

    error_rate: float
    stale_rate: float
    prediction_psi: float | None
    alerts: tuple[str, ...]

    @property
    def fingerprint(self) -> str:
        payload = {
            "error_rate": self.error_rate,
            "stale_rate": self.stale_rate,
            "prediction_psi": self.prediction_psi,
            "alerts": self.alerts,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def healthy(self) -> bool:
        return not self.alerts


def evaluate_monitoring(
    snapshot: MonitoringSnapshot,
    *,
    policy: MonitoringPolicy | None = None,
) -> MonitoringReport:
    """Evaluate telemetry against fixed operational thresholds.

    Alerts are observational only. They do not mutate models or authorize
    trades.
    """
    if not isinstance(snapshot, MonitoringSnapshot):
        raise TypeError("snapshot must be a MonitoringSnapshot")
    policy = policy or MonitoringPolicy()

    denominator = max(snapshot.total_events, 1)
    error_rate = snapshot.failed_events / denominator
    stale_rate = snapshot.stale_events / denominator

    psi = None
    if snapshot.reference_probabilities and snapshot.current_probabilities:
        psi = population_stability_index(
            list(snapshot.reference_probabilities),
            list(snapshot.current_probabilities),
        )

    alerts: list[str] = []
    if error_rate > policy.max_error_rate:
        alerts.append("ERROR_RATE_EXCEEDED")
    if stale_rate > policy.max_stale_rate:
        alerts.append("STALE_RATE_EXCEEDED")
    if psi is not None and psi > policy.max_prediction_psi:
        alerts.append("PREDICTION_DRIFT_EXCEEDED")

    return MonitoringReport(
        error_rate=error_rate,
        stale_rate=stale_rate,
        prediction_psi=psi,
        alerts=tuple(alerts),
    )
