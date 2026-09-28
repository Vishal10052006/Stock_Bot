from __future__ import annotations

"""Read-only adapters from existing subsystem telemetry into MonitoringPipeline.

Adapters deliberately accept protocol-shaped objects instead of owning or
mutating Market Bot, Analysis Bot, or data-pipeline state.
"""

from typing import Any

from .features import FeatureMonitoringSnapshot
from .health import ComponentHealth, HealthStatus
from .system import SystemMonitoringSnapshot


def market_health(metrics: Any) -> ComponentHealth:
    """Convert Market Bot observability metrics to central health."""
    status = (
        HealthStatus.HEALTHY
        if bool(metrics.success)
        else HealthStatus.UNHEALTHY
    )
    return ComponentHealth(
        component="market_bot",
        status=status,
        observed_at=str(metrics.timestamp),
        latency_seconds=float(metrics.latency_seconds),
        message="market context observed" if metrics.success else "market observation failed",
        metadata={
            "benchmark": str(metrics.benchmark),
            "availability": str(metrics.availability),
            "quality": metrics.quality,
            "regime": metrics.regime,
            "market_version": str(metrics.market_version),
        },
    )


def analysis_health(metrics: Any) -> ComponentHealth:
    """Convert Analysis Bot observability metrics to central health."""
    status = (
        HealthStatus.HEALTHY
        if bool(metrics.success) and float(metrics.completeness) >= 1.0
        else HealthStatus.DEGRADED
        if bool(metrics.success)
        else HealthStatus.UNHEALTHY
    )
    return ComponentHealth(
        component="analysis_bot",
        status=status,
        observed_at="analysis-observation",
        latency_seconds=float(metrics.latency_seconds),
        message="analysis context observed",
        metadata={
            "feature_count": int(metrics.feature_count),
            "missing_or_invalid": int(metrics.missing_or_invalid),
            "completeness": float(metrics.completeness),
            "analysis_version": str(metrics.analysis_version),
        },
    )


def data_quality_snapshot(snapshot: Any) -> SystemMonitoringSnapshot:
    """Map the existing Market data-quality snapshot without mutation."""
    return SystemMonitoringSnapshot(
        total_events=int(snapshot.events_received),
        failed_events=int(snapshot.events_rejected),
        stale_events=int(snapshot.stale_events),
        duplicate_events=int(snapshot.duplicate_events),
        invalid_events=int(snapshot.events_rejected),
        missing_data_gaps=int(snapshot.missing_data_gaps),
        latency_avg_ms=(
            None
            if snapshot.latency_avg_ms is None
            else float(snapshot.latency_avg_ms)
        ),
        latency_p95_ms=(
            None
            if snapshot.latency_p95_ms is None
            else float(snapshot.latency_p95_ms)
        ),
    )


def analysis_feature_snapshot(metrics: Any) -> FeatureMonitoringSnapshot:
    """Map Analysis Bot feature-quality telemetry to feature monitoring."""
    return FeatureMonitoringSnapshot(
        feature_count=int(metrics.feature_count),
        invalid_count=int(metrics.missing_or_invalid),
        missing_count=int(metrics.missing_or_invalid),
    )
