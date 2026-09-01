"""Tests for real-time market-data quality metrics."""

import pytest

from market.data.metrics import DataQualityMetrics
from market.data.validation import EventValidationResult


def make_result(
    *,
    valid: bool = True,
    stale: bool = False,
    duplicate: bool = False,
    latency_ms: float = 100.0,
) -> EventValidationResult:
    """Build a deterministic validation result for metrics tests."""
    return EventValidationResult(
        valid=valid,
        stale=stale,
        duplicate=duplicate,
        latency_ms=latency_ms,
    )


def test_valid_events_are_counted():
    """Accepted events should increment the received and accepted counters."""
    metrics = DataQualityMetrics()

    metrics.record_validation(
        make_result(
            valid=True,
            latency_ms=100.0,
        )
    )

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 1
    assert snapshot.events_accepted == 1
    assert snapshot.events_rejected == 0


def test_rejected_stale_and_duplicate_events_are_counted():
    """Validation failures should be categorized correctly."""
    metrics = DataQualityMetrics()

    metrics.record_validation(
        make_result(
            valid=False,
            stale=True,
            latency_ms=5000.0,
        )
    )

    metrics.record_validation(
        make_result(
            valid=False,
            duplicate=True,
            latency_ms=150.0,
        )
    )

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 2
    assert snapshot.events_accepted == 0
    assert snapshot.events_rejected == 2
    assert snapshot.stale_events == 1
    assert snapshot.duplicate_events == 1


def test_latency_statistics_are_calculated():
    """Latency metrics should expose useful aggregate statistics."""
    metrics = DataQualityMetrics()

    for latency in [10.0, 20.0, 30.0, 40.0, 100.0]:
        metrics.record_validation(
            make_result(latency_ms=latency)
        )

    snapshot = metrics.snapshot()

    assert snapshot.latency_sample_count == 5
    assert snapshot.latency_avg_ms == pytest.approx(40.0)
    assert snapshot.latency_min_ms == pytest.approx(10.0)
    assert snapshot.latency_max_ms == pytest.approx(100.0)
    assert snapshot.latency_p95_ms == pytest.approx(100.0)


def test_negative_latency_is_recorded_as_clock_skew():
    """Negative latency should be observable as a clock-skew condition."""
    metrics = DataQualityMetrics()

    metrics.record_validation(
        make_result(
            latency_ms=-400.0,
        )
    )

    snapshot = metrics.snapshot()

    assert snapshot.clock_skew_events == 1


def test_connection_and_reconnect_metrics_are_recorded():
    """Connection failures and reconnect outcomes should be measurable."""
    metrics = DataQualityMetrics()

    metrics.record_connection_failure()

    metrics.record_reconnect_attempt()
    metrics.record_reconnect_success()

    metrics.record_reconnect_attempt()
    metrics.record_reconnect_failure()

    snapshot = metrics.snapshot()

    assert snapshot.connection_failures == 1
    assert snapshot.reconnect_attempts == 2
    assert snapshot.reconnect_successes == 1
    assert snapshot.reconnect_failures == 1


def test_missing_data_gap_is_recorded_explicitly():
    """Missing-data detection should be explicit rather than inferred."""
    metrics = DataQualityMetrics()

    metrics.record_missing_data_gap()
    metrics.record_missing_data_gap()

    snapshot = metrics.snapshot()

    assert snapshot.missing_data_gaps == 2


def test_empty_metrics_have_no_latency_statistics():
    """Latency statistics should be None until samples exist."""
    metrics = DataQualityMetrics()

    snapshot = metrics.snapshot()

    assert snapshot.latency_sample_count == 0
    assert snapshot.latency_avg_ms is None
    assert snapshot.latency_min_ms is None
    assert snapshot.latency_max_ms is None
    assert snapshot.latency_p95_ms is None


def test_reset_clears_all_metrics():
    """Reset should return the collector to its initial state."""
    metrics = DataQualityMetrics()

    metrics.record_validation(make_result())
    metrics.record_connection_failure()
    metrics.record_reconnect_attempt()
    metrics.record_missing_data_gap()

    metrics.reset()

    snapshot = metrics.snapshot()

    assert snapshot.events_received == 0
    assert snapshot.events_accepted == 0
    assert snapshot.connection_failures == 0
    assert snapshot.reconnect_attempts == 0
    assert snapshot.missing_data_gaps == 0
