"""Dashboard/report builders for the STOCK_BOT monitoring engine."""

from __future__ import annotations

from typing import Iterable, Mapping

from monitoring.models import MonitoringReport, MonitoringSnapshot, SystemHealth
from monitoring.performance import performance_from_records


def build_trade_report(
    *,
    snapshot: MonitoringSnapshot,
    health: SystemHealth,
    alerts: tuple,
    drift: tuple,
) -> MonitoringReport:
    """Build a dashboard-safe immutable report."""
    return MonitoringReport(
        timestamp=snapshot.timestamp,
        system_health=health,
        snapshot=snapshot,
        alerts=tuple(alerts),
        drift=tuple(drift),
    )


def performance_summary(records: Iterable[object]) -> Mapping[str, object]:
    """Return JSON-safe performance metrics for dashboards."""
    return {
        "performance": performance_from_records(records),
    }
