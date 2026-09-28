from __future__ import annotations
from dataclasses import dataclass
import math
from .drift import DriftReport, calculate_psi

@dataclass(frozen=True, slots=True)
class ModelMonitoringSnapshot:
    """Observed model telemetry for one monitoring window."""
    model_version: str
    prediction_count: int
    labeled_count: int = 0
    correct_count: int = 0
    log_loss: float | None = None
    brier_score: float | None = None
    expected_calibration_error: float | None = None
    reference_probabilities: tuple[float, ...] = ()
    current_probabilities: tuple[float, ...] = ()
    def __post_init__(self) -> None:
        if not self.model_version.strip() or self.prediction_count < 0:
            raise ValueError("invalid model monitoring identity/count")
        if self.labeled_count < 0 or self.correct_count < 0 or self.correct_count > self.labeled_count:
            raise ValueError("invalid label counters")
        for value in (self.log_loss, self.brier_score, self.expected_calibration_error):
            if value is not None and (not math.isfinite(float(value)) or float(value) < 0):
                raise ValueError("model metric must be finite and non-negative")
        for value in (*self.reference_probabilities, *self.current_probabilities):
            if not math.isfinite(float(value)):
                raise ValueError("probabilities must be finite")

def evaluate_model_monitoring(snapshot: ModelMonitoringSnapshot, *, max_log_loss: float | None = None, max_ece: float | None = None, max_psi: float = 0.20, warning_psi: float | None = None) -> tuple[dict[str, float | int | None], tuple[DriftReport, ...], tuple[str, ...]]:
    """Evaluate model health without changing model state."""
    if max_psi < 0 or (warning_psi is not None and warning_psi < 0) or (warning_psi is not None and warning_psi > max_psi):
        raise ValueError("invalid model drift thresholds")
    metrics = {
        "prediction_count": snapshot.prediction_count,
        "labeled_count": snapshot.labeled_count,
        "accuracy": snapshot.correct_count / snapshot.labeled_count if snapshot.labeled_count else None,
        "log_loss": snapshot.log_loss,
        "brier_score": snapshot.brier_score,
        "expected_calibration_error": snapshot.expected_calibration_error,
    }
    alerts: list[str] = []
    if max_log_loss is not None and snapshot.log_loss is not None and snapshot.log_loss > max_log_loss:
        alerts.append("MODEL_LOG_LOSS_EXCEEDED")
    if max_ece is not None and snapshot.expected_calibration_error is not None and snapshot.expected_calibration_error > max_ece:
        alerts.append("MODEL_CALIBRATION_DRIFT")
    reports: list[DriftReport] = []
    if snapshot.reference_probabilities and snapshot.current_probabilities:
        psi = calculate_psi(list(snapshot.reference_probabilities), list(snapshot.current_probabilities))
        status = "CRITICAL" if psi > max_psi else "WARNING" if warning_psi is not None and psi > warning_psi else "OK"
        reports.append(DriftReport("prediction_probability", psi, len(snapshot.reference_probabilities), len(snapshot.current_probabilities), status))
        metrics["prediction_psi"] = psi
        if status == "CRITICAL": alerts.append("PREDICTION_DRIFT_EXCEEDED")
        elif status == "WARNING": alerts.append("PREDICTION_DRIFT_WARNING")
    return metrics, tuple(reports), tuple(alerts)
