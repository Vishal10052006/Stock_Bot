"""Phase 23 continuous model monitoring boundary.

This module is observational only. It aggregates model-health observations,
detects explicit degradation/drift conditions, and emits immutable monitoring
windows. It cannot mutate a model, strategy, Risk, Safety, or Execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ModelObservation:
    """One timestamped model observation."""

    timestamp: str
    model_version: str
    prediction_count: int
    labeled_count: int = 0
    correct_count: int = 0
    log_loss: float | None = None
    calibration_error: float | None = None
    prediction_drift: float | None = None

    def __post_init__(self) -> None:
        if not self.timestamp.strip() or not self.model_version.strip():
            raise ValueError("timestamp and model_version must not be empty")
        for name in ("prediction_count", "labeled_count", "correct_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.correct_count > self.labeled_count:
            raise ValueError("correct_count cannot exceed labeled_count")
        for name in ("log_loss", "calibration_error", "prediction_drift"):
            value = getattr(self, name)
            if value is not None and (
                not math.isfinite(float(value)) or float(value) < 0
            ):
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class MonitoringThresholds:
    """Explicit degradation thresholds; thresholds never change model state."""

    min_accuracy: float | None = None
    max_log_loss: float | None = None
    max_calibration_error: float | None = None
    max_prediction_drift: float | None = 0.20

    def __post_init__(self) -> None:
        for name in (
            "min_accuracy",
            "max_log_loss",
            "max_calibration_error",
            "max_prediction_drift",
        ):
            value = getattr(self, name)
            if value is not None and (
                not math.isfinite(float(value)) or float(value) < 0
            ):
                raise ValueError(f"{name} must be finite and non-negative")
        if self.min_accuracy is not None and self.min_accuracy > 1:
            raise ValueError("min_accuracy cannot exceed 1")


@dataclass(frozen=True, slots=True)
class MonitoringWindow:
    """Immutable aggregate of one continuous-monitoring window."""

    model_version: str
    observation_count: int
    prediction_count: int
    labeled_count: int
    accuracy: float | None
    mean_log_loss: float | None
    mean_calibration_error: float | None
    max_prediction_drift: float | None
    alerts: tuple[str, ...]
    first_timestamp: str
    last_timestamp: str

    @property
    def healthy(self) -> bool:
        return not self.alerts


class ContinuousModelMonitor:
    """Aggregate chronological observations and report explicit degradation."""

    VERSION = "MODEL-MONITOR-v1.0"

    def __init__(self, *, thresholds: MonitoringThresholds | None = None) -> None:
        self.thresholds = thresholds or MonitoringThresholds()
        self._observations: list[ModelObservation] = []

    def observe(self, observation: ModelObservation) -> MonitoringWindow:
        """Accept one observation; timestamps must be non-decreasing."""
        if self._observations:
            previous = self._observations[-1]
            if observation.timestamp < previous.timestamp:
                raise ValueError("monitoring observations must be chronological")

        self._observations.append(observation)
        return self.snapshot()

    def observe_many(
        self,
        observations: Iterable[ModelObservation],
    ) -> MonitoringWindow:
        for observation in observations:
            self.observe(observation)
        return self.snapshot()

    def snapshot(self) -> MonitoringWindow:
        if not self._observations:
            raise ValueError("cannot snapshot an empty monitoring window")

        observations = tuple(self._observations)
        model_versions = {item.model_version for item in observations}
        if len(model_versions) != 1:
            raise ValueError("one monitoring window must contain one model version")

        prediction_count = sum(item.prediction_count for item in observations)
        labeled_count = sum(item.labeled_count for item in observations)
        correct_count = sum(item.correct_count for item in observations)
        accuracy = (
            correct_count / labeled_count if labeled_count else None
        )

        losses = [item.log_loss for item in observations if item.log_loss is not None]
        calibrations = [
            item.calibration_error
            for item in observations
            if item.calibration_error is not None
        ]
        drifts = [
            item.prediction_drift
            for item in observations
            if item.prediction_drift is not None
        ]

        mean_log_loss = sum(losses) / len(losses) if losses else None
        mean_calibration = (
            sum(calibrations) / len(calibrations) if calibrations else None
        )
        max_drift = max(drifts) if drifts else None

        alerts: list[str] = []
        t = self.thresholds
        if t.min_accuracy is not None and accuracy is not None and accuracy < t.min_accuracy:
            alerts.append("MODEL_ACCURACY_DEGRADED")
        if t.max_log_loss is not None and mean_log_loss is not None and mean_log_loss > t.max_log_loss:
            alerts.append("MODEL_LOG_LOSS_DEGRADED")
        if (
            t.max_calibration_error is not None
            and mean_calibration is not None
            and mean_calibration > t.max_calibration_error
        ):
            alerts.append("MODEL_CALIBRATION_DEGRADED")
        if (
            t.max_prediction_drift is not None
            and max_drift is not None
            and max_drift > t.max_prediction_drift
        ):
            alerts.append("MODEL_PREDICTION_DRIFT")

        return MonitoringWindow(
            model_version=observations[0].model_version,
            observation_count=len(observations),
            prediction_count=prediction_count,
            labeled_count=labeled_count,
            accuracy=accuracy,
            mean_log_loss=mean_log_loss,
            mean_calibration_error=mean_calibration,
            max_prediction_drift=max_drift,
            alerts=tuple(alerts),
            first_timestamp=observations[0].timestamp,
            last_timestamp=observations[-1].timestamp,
        )

    def observations(self) -> tuple[ModelObservation, ...]:
        return tuple(self._observations)


__all__ = [
    "ContinuousModelMonitor",
    "ModelObservation",
    "MonitoringThresholds",
    "MonitoringWindow",
]
