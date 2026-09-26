"""Phase 23 continuous model-monitoring session.

Wraps the existing observational MonitoringRuntime with a chronological,
append-only model-monitoring evidence stream. This module never mutates a
model, promotes a candidate, changes Strategy/Risk, or authorizes execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from monitoring import ModelMonitoringSnapshot, MonitoringRuntime


@dataclass(frozen=True, slots=True)
class ModelMonitoringObservation:
    """Immutable model-health observation with deterministic identity."""

    observed_at: datetime
    model: ModelMonitoringSnapshot
    alerts: tuple[str, ...] = ()
    live_broker_order_submission: bool = False

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.live_broker_order_submission:
            raise ValueError("model monitoring cannot enable live broker orders")
        if not self.model.model_version.strip():
            raise ValueError("model_version must not be empty")

    def payload(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at.isoformat(),
            "model_version": self.model.model_version,
            "prediction_count": self.model.prediction_count,
            "labeled_count": self.model.labeled_count,
            "correct_count": self.model.correct_count,
            "log_loss": self.model.log_loss,
            "brier_score": self.model.brier_score,
            "expected_calibration_error": self.model.expected_calibration_error,
            "reference_probabilities": list(self.model.reference_probabilities),
            "current_probabilities": list(self.model.current_probabilities),
            "alerts": list(self.alerts),
            "live_broker_order_submission": False,
        }

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ContinuousModelMonitoring:
    """Chronological model-health collector backed by the existing monitor."""

    def __init__(
        self,
        *,
        runtime: MonitoringRuntime | None = None,
        journal_path: str | Path | None = None,
    ) -> None:
        self.runtime = runtime or MonitoringRuntime()
        self.journal_path = Path(journal_path) if journal_path is not None else None
        self._observations: list[ModelMonitoringObservation] = []

    def observe(
        self,
        snapshot: ModelMonitoringSnapshot,
        *,
        observed_at: datetime | None = None,
    ) -> ModelMonitoringObservation:
        """Record one model-health window in strict chronological order."""
        timestamp = observed_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        timestamp = timestamp.astimezone(timezone.utc)

        if self._observations and timestamp <= self._observations[-1].observed_at:
            raise ValueError("model observations must have strictly increasing timestamps")

        before_alerts = len(self.runtime.engine.snapshot().alerts)
        self.runtime.observe_model(snapshot)
        monitoring_snapshot = self.runtime.engine.snapshot()
        alerts = tuple(
            alert.code
            for alert in monitoring_snapshot.alerts[before_alerts:]
        )
        observation = ModelMonitoringObservation(
            observed_at=timestamp,
            model=snapshot,
            alerts=alerts,
        )
        self._observations.append(observation)
        self._append(observation)
        return observation

    def observations(self) -> tuple[ModelMonitoringObservation, ...]:
        return tuple(self._observations)

    def latest(self) -> ModelMonitoringObservation | None:
        return self._observations[-1] if self._observations else None

    def evidence(self) -> dict[str, Any]:
        latest = self.latest()
        return {
            "observation_count": len(self._observations),
            "latest_model_version": latest.model.model_version if latest else None,
            "latest_observed_at": latest.observed_at.isoformat() if latest else None,
            "alert_count": sum(len(item.alerts) for item in self._observations),
            "journal_path": str(self.journal_path) if self.journal_path else None,
            "live_broker_order_submission": False,
        }

    def _append(self, observation: ModelMonitoringObservation) -> None:
        if self.journal_path is None:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = observation.payload()
        payload["fingerprint"] = observation.fingerprint
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
