"""Tests for PaperExperimentMetrics and report generator."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.paper.lifecycle import TradeLifecycleStatus, TradeOutcome
from trading.paper.metrics import calculate_paper_metrics, generate_experiment_report
from trading.strategy.models import StrategyDirection


def _make_outcome(
    pnl: float,
    direction: StrategyDirection = StrategyDirection.LONG,
    holding_min: float = 15.0,
    symbol: str = "RELIANCE",
) -> TradeOutcome:
    ts1 = pd.Timestamp("2026-09-29 10:00:00+05:30")
    ts2 = ts1 + pd.Timedelta(minutes=holding_min)
    entry_p = 100.0
    exit_p = entry_p + (pnl / 10.0) if direction is StrategyDirection.LONG else entry_p - (pnl / 10.0)
    return TradeOutcome(
        symbol=symbol,
        direction=direction,
        entry_time=ts1,
        exit_time=ts2,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=10.0,
        gross_pnl=pnl,
        fees=0.0,
        slippage_cost=0.0,
        net_pnl=pnl,
        holding_minutes=holding_min,
        mae=-5.0,
        mfe=15.0,
        status=TradeLifecycleStatus.CLOSED,
    )


def test_calculate_metrics_10_trades_win_rate():
    # 6 wins (+20 each), 4 losses (-10 each) -> total 10 trades, 60% win rate
    outcomes = [
        _make_outcome(20.0, StrategyDirection.LONG),
        _make_outcome(20.0, StrategyDirection.LONG),
        _make_outcome(20.0, StrategyDirection.LONG),
        _make_outcome(-10.0, StrategyDirection.LONG),
        _make_outcome(20.0, StrategyDirection.SHORT),
        _make_outcome(-10.0, StrategyDirection.SHORT),
        _make_outcome(20.0, StrategyDirection.SHORT),
        _make_outcome(-10.0, StrategyDirection.SHORT),
        _make_outcome(20.0, StrategyDirection.LONG),
        _make_outcome(-10.0, StrategyDirection.LONG),
    ]

    metrics = calculate_paper_metrics(outcomes, initial_equity=100_000.0)

    assert metrics.total_trades == 10
    assert metrics.wins == 6
    assert metrics.losses == 4
    assert metrics.win_rate_pct == 60.0
    assert metrics.net_pnl == 80.0   # (6 * 20) - (4 * 10) = 120 - 40 = 80
    assert metrics.average_win == 20.0
    assert metrics.average_loss == 10.0
    assert metrics.profit_factor == 3.0   # 120 / 40
    assert metrics.expectancy == 8.0      # 0.6 * 20 - 0.4 * 10 = 12 - 4 = 8

    # Direction breakdown
    assert metrics.long_trades == 6
    assert metrics.long_wins == 4
    assert metrics.short_trades == 4
    assert metrics.short_wins == 2


def test_generate_report_formatting():
    outcomes = [
        _make_outcome(50.0, StrategyDirection.LONG),
        _make_outcome(-25.0, StrategyDirection.SHORT),
    ]
    metrics = calculate_paper_metrics(outcomes)
    report = generate_experiment_report(
        metrics,
        experiment_id="PAPER-LIVE-TEST",
        start_time="2026-09-29 09:15:00",
        end_time="2026-09-29 15:30:00",
    )

    assert "STOCK_BOT PAPER EXPERIMENT" in report
    assert "PAPER-LIVE-TEST" in report
    assert "Trades               2" in report
    assert "Wins                 1" in report
    assert "Win Rate             50.00%" in report
    assert "Live Broker Orders:  0" in report
