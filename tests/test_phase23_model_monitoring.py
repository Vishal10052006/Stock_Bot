from datetime import datetime, timezone

import pytest

from monitoring import ModelMonitoringSnapshot
from runtime.model_monitoring import ContinuousModelMonitoring


def _snapshot(version: str = "model-v1") -> ModelMonitoringSnapshot:
    return ModelMonitoringSnapshot(
        model_version=version,
        prediction_count=100,
        labeled_count=80,
        correct_count=60,
        log_loss=0.4,
        expected_calibration_error=0.05,
        reference_probabilities=(0.2, 0.4, 0.6, 0.8),
        current_probabilities=(0.2, 0.4, 0.6, 0.8),
    )


def test_phase23_records_chronological_model_observations(tmp_path) -> None:
    monitor = ContinuousModelMonitoring(journal_path=tmp_path / "model.jsonl")

    first = monitor.observe(
        _snapshot(),
        observed_at=datetime(2026, 9, 25, 9, 15, tzinfo=timezone.utc),
    )
    second = monitor.observe(
        _snapshot("model-v1"),
        observed_at=datetime(2026, 9, 25, 9, 20, tzinfo=timezone.utc),
    )

    assert first.fingerprint
    assert second.fingerprint
    assert monitor.evidence()["observation_count"] == 2
    assert monitor.evidence()["live_broker_order_submission"] is False
    assert len((tmp_path / "model.jsonl").read_text().splitlines()) == 2


def test_phase23_rejects_non_monotonic_observations() -> None:
    monitor = ContinuousModelMonitoring()
    timestamp = datetime(2026, 9, 25, 9, 20, tzinfo=timezone.utc)

    monitor.observe(_snapshot(), observed_at=timestamp)

    with pytest.raises(ValueError, match="strictly increasing"):
        monitor.observe(_snapshot(), observed_at=timestamp)


def test_phase23_never_allows_live_broker_submission() -> None:
    monitor = ContinuousModelMonitoring()
    observation = monitor.observe(
        _snapshot(),
        observed_at=datetime(2026, 9, 25, 9, 15, tzinfo=timezone.utc),
    )

    assert observation.live_broker_order_submission is False
    assert monitor.evidence()["live_broker_order_submission"] is False
