"""AB-41 backtest performance metrics."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from trading.paper.lifecycle import TradeOutcome


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    """Immutable aggregate performance report."""

    trade_count: int
    winning_trades: int
    losing_trades: int
    gross_pnl: float
    net_pnl: float
    total_fees: float
    total_slippage: float
    win_rate: float
    average_win: float
    average_loss: float
    profit_factor: float
    expectancy: float
    maximum_drawdown: float
    sharpe_ratio: float
    exposure_minutes: float
    turnover: float


def calculate_metrics(
    outcomes: tuple[TradeOutcome, ...] | list[TradeOutcome],
) -> BacktestMetrics:
    """Calculate deterministic trade-level performance metrics."""

    trades = tuple(outcomes)

    if not trades:
        return BacktestMetrics(
            trade_count=0,
            winning_trades=0,
            losing_trades=0,
            gross_pnl=0.0,
            net_pnl=0.0,
            total_fees=0.0,
            total_slippage=0.0,
            win_rate=0.0,
            average_win=0.0,
            average_loss=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            maximum_drawdown=0.0,
            sharpe_ratio=0.0,
            exposure_minutes=0.0,
            turnover=0.0,
        )

    pnls = np.asarray(
        [trade.net_pnl for trade in trades],
        dtype=float,
    )

    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    gross_pnl = sum(trade.gross_pnl for trade in trades)
    net_pnl = sum(trade.net_pnl for trade in trades)
    fees = sum(trade.fees for trade in trades)
    slippage = sum(trade.slippage_cost for trade in trades)

    win_rate = float(len(wins) / len(pnls))

    average_win = (
        float(wins.mean())
        if len(wins)
        else 0.0
    )

    average_loss = (
        float(losses.mean())
        if len(losses)
        else 0.0
    )

    gross_wins = float(wins.sum()) if len(wins) else 0.0
    gross_losses = abs(float(losses.sum())) if len(losses) else 0.0

    if gross_losses > 0:
        profit_factor = gross_wins / gross_losses
    elif gross_wins > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0

    expectancy = float(pnls.mean())

    equity = np.cumsum(pnls)
    peaks = np.maximum.accumulate(
        np.concatenate(([0.0], equity))
    )[1:]
    drawdowns = peaks - equity
    maximum_drawdown = (
        float(drawdowns.max())
        if len(drawdowns)
        else 0.0
    )

    if len(pnls) > 1 and float(pnls.std(ddof=1)) > 0:
        sharpe_ratio = float(
            pnls.mean() / pnls.std(ddof=1)
            * math.sqrt(len(pnls))
        )
    else:
        sharpe_ratio = 0.0

    exposure_minutes = sum(
        trade.holding_minutes
        for trade in trades
    )

    turnover = sum(
        trade.entry_price * trade.quantity
        + trade.exit_price * trade.quantity
        for trade in trades
    )

    return BacktestMetrics(
        trade_count=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        gross_pnl=float(gross_pnl),
        net_pnl=float(net_pnl),
        total_fees=float(fees),
        total_slippage=float(slippage),
        win_rate=win_rate,
        average_win=average_win,
        average_loss=average_loss,
        profit_factor=profit_factor,
        expectancy=expectancy,
        maximum_drawdown=maximum_drawdown,
        sharpe_ratio=sharpe_ratio,
        exposure_minutes=float(exposure_minutes),
        turnover=float(turnover),
    )
