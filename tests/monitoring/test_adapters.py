from types import SimpleNamespace

from monitoring.adapters import (
    analysis_feature_snapshot,
    analysis_health,
    data_quality_snapshot,
    market_health,
)
from monitoring.health import HealthStatus


def test_market_health_is_read_only_mapping() -> None:
    metrics = SimpleNamespace(
        success=True,
        timestamp="2026-09-24T10:00:00+00:00",
        latency_seconds=0.01,
        benchmark="NIFTY",
        availability="AVAILABLE",
        quality=0.99,
        regime="TREND",
        market_version="market-v1",
    )

    health = market_health(metrics)

    assert health.component == "market_bot"
    assert health.status is HealthStatus.HEALTHY
    assert health.metadata["market_version"] == "market-v1"


def test_analysis_health_marks_incomplete_context_degraded() -> None:
    metrics = SimpleNamespace(
        success=True,
        latency_seconds=0.02,
        feature_count=20,
        missing_or_invalid=2,
        completeness=0.90,
        analysis_version="analysis-v1",
    )

    health = analysis_health(metrics)

    assert health.status is HealthStatus.DEGRADED
    assert health.metadata["feature_count"] == 20


def test_data_quality_adapter_preserves_operational_counts() -> None:
    snapshot = SimpleNamespace(
        events_received=100,
        events_rejected=5,
        stale_events=12,
        duplicate_events=3,
        missing_data_gaps=2,
        latency_avg_ms=4.0,
        latency_p95_ms=8.0,
    )

    mapped = data_quality_snapshot(snapshot)

    assert mapped.total_events == 100
    assert mapped.failed_events == 5
    assert mapped.stale_events == 12
    assert mapped.latency_p95_ms == 8.0


def test_analysis_feature_adapter_maps_quality_counters() -> None:
    metrics = SimpleNamespace(
        feature_count=30,
        missing_or_invalid=3,
    )

    mapped = analysis_feature_snapshot(metrics)

    assert mapped.feature_count == 30
    assert mapped.invalid_count == 3
    assert mapped.missing_count == 3
