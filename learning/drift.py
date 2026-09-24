"""Convert monitoring drift into bounded learning investigations.

Drift triggers investigation only. It never retrains, promotes, changes risk,
or contacts the broker automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from experiments.monitoring import MonitoringReport

from .self_learning_models import FailureClass


@dataclass(frozen=True, slots=True)
class DriftInvestigation:
    """Immutable research investigation generated from monitoring evidence."""

    investigation_id: str
    alerts: tuple[str, ...]
    failure_class: FailureClass
    hypothesis: str
    source_monitoring_fingerprint: str

    def __post_init__(self) -> None:
        if not self.investigation_id.strip():
            raise ValueError("investigation_id must be non-empty")
        if not self.alerts:
            raise ValueError("alerts must not be empty")
        if len(self.source_monitoring_fingerprint) != 64:
            raise ValueError("source_monitoring_fingerprint must be SHA-256")

    @property
    def fingerprint(self) -> str:
        """Return deterministic investigation identity."""
        payload = {
            "investigation_id": self.investigation_id,
            "alerts": list(self.alerts),
            "failure_class": self.failure_class.value,
            "hypothesis": self.hypothesis,
            "source_monitoring_fingerprint": self.source_monitoring_fingerprint,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()


class DriftInvestigator:
    """Create a research hypothesis from observational drift evidence."""

    def investigate(
        self,
        report: MonitoringReport,
        *,
        investigation_id: str,
    ) -> DriftInvestigation | None:
        """Create an investigation or return None when monitoring is healthy."""
        if not isinstance(report, MonitoringReport):
            raise TypeError("report must be a MonitoringReport")
        if not report.alerts:
            return None

        alerts = tuple(report.alerts)
        alert_set = set(alerts)

        if "PREDICTION_DRIFT_EXCEEDED" in alert_set:
            failure_class = FailureClass.CALIBRATION_FAILURE
            hypothesis = (
                "Investigate whether prediction-distribution drift is associated "
                "with degradation in outcome quality or probability calibration."
            )
        elif "ERROR_RATE_EXCEEDED" in alert_set:
            failure_class = FailureClass.INFRASTRUCTURE_FAILURE
            hypothesis = (
                "Investigate whether operational errors are reducing the integrity "
                "or completeness of the observed trading evidence."
            )
        else:
            failure_class = FailureClass.DATA_FAILURE
            hypothesis = (
                "Investigate whether stale or incomplete market data is associated "
                "with the observed monitoring degradation."
            )

        return DriftInvestigation(
            investigation_id=investigation_id,
            alerts=alerts,
            failure_class=failure_class,
            hypothesis=hypothesis,
            source_monitoring_fingerprint=report.fingerprint,
        )
