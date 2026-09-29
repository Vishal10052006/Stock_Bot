"""Phase 23 continuous model monitoring tests."""

import pytest

from monitoring.continuous import (
    ContinuousModelMonitor,
    ModelObservation,
    MonitoringThresholds,
)


def _obs(
    timestamp: str,
    *,
    accuracy_count: tuple[int, int] = (9, 10),
    log_loss: float = 0.20,
    calibration: float = 0.03,
    drift: float = 0.05,
) -> ModelObservation:
    correct, labeled = accuracy_count
    return ModelObservation(
        timestamp=timestamp,
        model_version="model-v1",
        prediction_count=10,
        labeled_count=labeled,
        correct_count=correct,
        log_loss=log_loss,
        calibration_error=calibration,
        prediction_drift=drift,
    )


def test_monitor_aggregates_chronological_observations() -> None:
    monitor = ContinuousModelMonitor()
    window = monitor.observe_many(
        (
            _obs("2026-09-25T09:20:00+05:30"),
            _obs("2026-09-25T09:25:00+05:30"),
        )
    )

    assert window.observation_count == 2
    assert window.prediction_count == 20
    assert window.accuracy == 0.9
    assert window.mean_log_loss == 0.20
    assert window.max_prediction_drift == 0.05
    assert window.healthy


def test_monitor_rejects_out_of_order_observations() -> None:
    monitor = ContinuousModelMonitor()
    monitor.observe(_obs("2026-09-25T09:25:00+05:30"))

    with pytest.raises(ValueError, match="chronological"):
        monitor.observe(_obs("2026-09-25T09:20:00+05:30"))


def test_monitor_emits_explicit_degradation_alerts() -> None:
    monitor = ContinuousModelMonitor(
        thresholds=MonitoringThresholds(
            min_accuracy=0.80,
            max_log_loss=0.50,
            max_calibration_error=0.10,
            max_prediction_drift=0.20,
        )
    )

    window = monitor.observe(
        _obs(
            "2026-09-25T09:20:00+05:30",
            accuracy_count=(6, 10),
            log_loss=0.80,
            calibration=0.20,
            drift=0.35,
        )
    )

    assert set(window.alerts) == {
        "MODEL_ACCURACY_DEGRADED",
        "MODEL_LOG_LOSS_DEGRADED",
        "MODEL_CALIBRATION_DEGRADED",
        "MODEL_PREDICTION_DRIFT",
    }


def test_monitor_rejects_mixed_model_versions() -> None:
    monitor = ContinuousModelMonitor()
    monitor.observe(_obs("2026-09-25T09:20:00+05:30"))

    with pytest.raises(ValueError, match="one monitoring window"):
        monitor.observe(
            ModelObservation(
                timestamp="2026-09-25T09:21:00+05:30",
                model_version="model-v2",
                prediction_count=1,
            )
        )


def test_monitor_observation_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        ModelObservation(
            timestamp="2026-09-25T09:20:00+05:30",
            model_version="model-v1",
            prediction_count=1,
            labeled_count=1,
            correct_count=2,
        )


def test_monitor_does_not_authorize_execution() -> None:
    monitor = ContinuousModelMonitor()
    window = monitor.observe(_obs("2026-09-25T09:20:00+05:30"))

    assert not hasattr(window, "authorization")
    assert not hasattr(window, "order")
