"""M-5/M-8 trading performance aggregation from journal outcomes."""

from __future__ import annotations

from collections import defaultdict
from math import inf
from typing import Iterable, Mapping

from monitoring.models import PerformanceSnapshot


def performance_from_records(records: Iterable[object]) -> PerformanceSnapshot:
    """Aggregate completed TradeJournalRecord-compatible objects.

    The function intentionally relies on the journal outcome contract rather
    than reconstructing values from market data.
    """
    items = tuple(records)
    trade_count = len(items)
    if not items:
        return PerformanceSnapshot(
            trade_count=0,
            winning_trades=0,
            losing_trades=0,
            net_pnl=0.0,
            gross_pnl=0.0,
            fees=0.0,
            slippage_cost=0.0,
            expectancy=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            average_holding_minutes=0.0,
            average_mae=0.0,
            average_mfe=0.0,
        )

    net_pnls = [float(item.net_pnl) for item in items]
    gross_pnls = [float(item.gross_pnl) for item in items]
    fees = sum(float(item.fees) for item in items)
    slippage = sum(float(item.slippage_cost) for item in items)
    wins = [value for value in net_pnls if value > 0]
    losses = [value for value in net_pnls if value < 0]

    running = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in net_pnls:
        running += value
        peak = max(peak, running)
        max_drawdown = max(max_drawdown, peak - running)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = inf if gross_loss == 0 and gross_profit > 0 else (
        gross_profit / gross_loss if gross_loss else 0.0
    )

    return PerformanceSnapshot(
        trade_count=trade_count,
        winning_trades=len(wins),
        losing_trades=len(losses),
        net_pnl=sum(net_pnls),
        gross_pnl=sum(gross_pnls),
        fees=fees,
        slippage_cost=slippage,
        expectancy=sum(net_pnls) / trade_count,
        win_rate=len(wins) / trade_count,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        average_holding_minutes=sum(float(item.holding_minutes) for item in items) / trade_count,
        average_mae=sum(float(item.mae) for item in items) / trade_count,
        average_mfe=sum(float(item.mfe) for item in items) / trade_count,
    )


def grouped_net_pnl(records: Iterable[object], key: str) -> Mapping[str, float]:
    """Aggregate net P&L by a simple journal field."""
    result: dict[str, float] = defaultdict(float)
    for item in records:
        value = getattr(item, key)
        result[str(value)] += float(item.net_pnl)
    return dict(sorted(result.items()))
