"""Dashboard/report builders for the STOCK_BOT monitoring engine."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from monitoring.models import DriftReport, MonitoringReport, MonitoringSnapshot, SystemHealth
from monitoring.performance import performance_from_records


def build_trade_report(
    *,
    snapshot: MonitoringSnapshot,
    health: SystemHealth,
    alerts: Sequence,
    drift: Sequence[DriftReport],
) -> MonitoringReport:
    """Build one immutable dashboard/API-ready report."""
    return MonitoringReport(
        timestamp=snapshot.timestamp,
        system_health=health,
        snapshot=snapshot,
        alerts=tuple(alerts),
        drift=tuple(drift),
    )


def performance_summary(records: Iterable[object]) -> Mapping[str, object]:
    """Return JSON-safe performance metrics for dashboards."""
    performance = performance_from_records(records)
    return {
        "trade_count": performance.trade_count,
        "winning_trades": performance.winning_trades,
        "losing_trades": performance.losing_trades,
        "net_pnl": performance.net_pnl,
        "gross_pnl": performance.gross_pnl,
        "fees": performance.fees,
        "slippage_cost": performance.slippage_cost,
        "expectancy": performance.expectancy,
        "win_rate": performance.win_rate,
        "profit_factor": performance.profit_factor,
        "max_drawdown": performance.max_drawdown,
        "average_holding_minutes": performance.average_holding_minutes,
        "average_mae": performance.average_mae,
        "average_mfe": performance.average_mfe,
    }
