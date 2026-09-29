"""Empirical performance metrics and reporting for paper-trading experiments.

Calculates standard quantitative trading statistics:
- Win rate, Net P&L, Profit Factor, Expectancy, Max Drawdown
- Execution friction (gross P&L vs fees & slippage)
- Breakdowns by direction (LONG vs SHORT) and market regime (TREND_UP, etc.)
- Formats reproducible experiment reports matching STOCK_BOT specifications.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any, Mapping, Sequence

from trading.paper.lifecycle import TradeOutcome
from trading.strategy.models import StrategyDirection


@dataclass(frozen=True, slots=True)
class PaperExperimentMetrics:
    """Comprehensive performance metrics for a completed paper session."""

    total_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate_pct: float
    gross_pnl: float
    total_fees: float
    total_slippage: float
    net_pnl: float
    average_win: float
    average_loss: float
    win_loss_ratio: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_holding_minutes: float
    long_trades: int
    long_wins: int
    long_losses: int
    long_net_pnl: float
    long_win_rate_pct: float
    short_trades: int
    short_wins: int
    short_losses: int
    short_net_pnl: float
    short_win_rate_pct: float
    regime_breakdown: Mapping[str, Mapping[str, Any]]
    exit_reason_breakdown: Mapping[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a JSON-serializable dictionary."""
        data = asdict(self)
        for k, v in data.items():
            if isinstance(v, float) and not math.isfinite(v):
                data[k] = str(v)
        return data


def calculate_paper_metrics(
    outcomes: Sequence[TradeOutcome],
    *,
    initial_equity: float = 100_000.0,
    regimes: Mapping[str, str] | Sequence[str] | None = None,
    exit_reasons: Mapping[str, str] | None = None,
) -> PaperExperimentMetrics:
    """Compute empirical metrics from a chronological sequence of trade outcomes."""
    total_trades = len(outcomes)
    if total_trades == 0:
        return PaperExperimentMetrics(
            total_trades=0,
            wins=0,
            losses=0,
            breakevens=0,
            win_rate_pct=0.0,
            gross_pnl=0.0,
            total_fees=0.0,
            total_slippage=0.0,
            net_pnl=0.0,
            average_win=0.0,
            average_loss=0.0,
            win_loss_ratio=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            avg_holding_minutes=0.0,
            long_trades=0,
            long_wins=0,
            long_losses=0,
            long_net_pnl=0.0,
            long_win_rate_pct=0.0,
            short_trades=0,
            short_wins=0,
            short_losses=0,
            short_net_pnl=0.0,
            short_win_rate_pct=0.0,
            regime_breakdown={},
            exit_reason_breakdown={},
        )

    wins = sum(1 for o in outcomes if o.net_pnl > 1e-9)
    losses = sum(1 for o in outcomes if o.net_pnl < -1e-9)
    breakevens = total_trades - wins - losses
    win_rate_pct = (wins / total_trades) * 100.0

    gross_pnl = sum(o.gross_pnl for o in outcomes)
    total_fees = sum(o.fees for o in outcomes)
    total_slippage = sum(o.slippage_cost for o in outcomes)
    net_pnl = sum(o.net_pnl for o in outcomes)

    win_pnls = [o.net_pnl for o in outcomes if o.net_pnl > 1e-9]
    loss_pnls = [o.net_pnl for o in outcomes if o.net_pnl < -1e-9]

    sum_wins = sum(win_pnls)
    abs_sum_losses = abs(sum(loss_pnls))

    average_win = (sum_wins / len(win_pnls)) if win_pnls else 0.0
    average_loss = (abs_sum_losses / len(loss_pnls)) if loss_pnls else 0.0

    win_loss_ratio = (average_win / average_loss) if average_loss > 0 else (float("inf") if average_win > 0 else 0.0)
    profit_factor = (sum_wins / abs_sum_losses) if abs_sum_losses > 0 else (float("inf") if sum_wins > 0 else 0.0)

    win_rate = wins / total_trades
    loss_rate = losses / total_trades
    expectancy = (win_rate * average_win) - (loss_rate * average_loss)

    # Max Drawdown calculation from cumulative equity curve
    peak_equity = initial_equity
    running_equity = initial_equity
    max_drawdown = 0.0
    max_drawdown_pct = 0.0

    for o in outcomes:
        running_equity += o.net_pnl
        if running_equity > peak_equity:
            peak_equity = running_equity
        drawdown = peak_equity - running_equity
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_pct = (drawdown / peak_equity * 100.0) if peak_equity > 0 else 0.0

    avg_holding_minutes = sum(o.holding_minutes for o in outcomes) / total_trades

    # Long vs Short breakdown
    long_outcomes = [o for o in outcomes if o.direction is StrategyDirection.LONG]
    short_outcomes = [o for o in outcomes if o.direction is StrategyDirection.SHORT]

    long_trades = len(long_outcomes)
    long_wins = sum(1 for o in long_outcomes if o.net_pnl > 1e-9)
    long_losses = sum(1 for o in long_outcomes if o.net_pnl < -1e-9)
    long_net_pnl = sum(o.net_pnl for o in long_outcomes)
    long_win_rate_pct = (long_wins / long_trades * 100.0) if long_trades > 0 else 0.0

    short_trades = len(short_outcomes)
    short_wins = sum(1 for o in short_outcomes if o.net_pnl > 1e-9)
    short_losses = sum(1 for o in short_outcomes if o.net_pnl < -1e-9)
    short_net_pnl = sum(o.net_pnl for o in short_outcomes)
    short_win_rate_pct = (short_wins / short_trades * 100.0) if short_trades > 0 else 0.0

    # Regime breakdown
    regime_dict: dict[str, list[TradeOutcome]] = {}
    for idx, o in enumerate(outcomes):
        r_name = "UNKNOWN"
        if isinstance(regimes, Mapping) and o.symbol in regimes:
            r_name = regimes[o.symbol]
        elif isinstance(regimes, Sequence) and idx < len(regimes):
            r_name = regimes[idx]
        regime_dict.setdefault(r_name, []).append(o)

    regime_breakdown: dict[str, dict[str, Any]] = {}
    for r_name, r_outcomes in sorted(regime_dict.items()):
        r_count = len(r_outcomes)
        r_wins = sum(1 for x in r_outcomes if x.net_pnl > 1e-9)
        r_losses = sum(1 for x in r_outcomes if x.net_pnl < -1e-9)
        r_pnl = sum(x.net_pnl for x in r_outcomes)
        regime_breakdown[r_name] = {
            "trades": r_count,
            "wins": r_wins,
            "losses": r_losses,
            "win_rate_pct": (r_wins / r_count * 100.0) if r_count > 0 else 0.0,
            "net_pnl": r_pnl,
        }

    # Exit reason breakdown
    exit_reason_counts: dict[str, int] = {}
    if exit_reasons:
        for reason in exit_reasons.values():
            exit_reason_counts[reason] = exit_reason_counts.get(reason, 0) + 1

    return PaperExperimentMetrics(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        win_rate_pct=round(win_rate_pct, 2),
        gross_pnl=round(gross_pnl, 2),
        total_fees=round(total_fees, 2),
        total_slippage=round(total_slippage, 2),
        net_pnl=round(net_pnl, 2),
        average_win=round(average_win, 2),
        average_loss=round(average_loss, 2),
        win_loss_ratio=round(win_loss_ratio, 2) if math.isfinite(win_loss_ratio) else 999.0,
        profit_factor=round(profit_factor, 2) if math.isfinite(profit_factor) else 999.0,
        expectancy=round(expectancy, 2),
        max_drawdown=round(max_drawdown, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        avg_holding_minutes=round(avg_holding_minutes, 1),
        long_trades=long_trades,
        long_wins=long_wins,
        long_losses=long_losses,
        long_net_pnl=round(long_net_pnl, 2),
        long_win_rate_pct=round(long_win_rate_pct, 2),
        short_trades=short_trades,
        short_wins=short_wins,
        short_losses=short_losses,
        short_net_pnl=round(short_net_pnl, 2),
        short_win_rate_pct=round(short_win_rate_pct, 2),
        regime_breakdown=regime_breakdown,
        exit_reason_breakdown=exit_reason_counts,
    )


def generate_experiment_report(
    metrics: PaperExperimentMetrics,
    *,
    experiment_id: str,
    start_time: str,
    end_time: str,
    model_version: str = "v1.0",
    strategy_version: str = "STRAT-v1.0",
    risk_version: str = "RISK-v1.0",
    feed_name: str = "Upstox",
    timeframe: str = "5m",
    live_broker_orders: int = 0,
) -> str:
    """Format an auditable text report matching the STOCK_BOT experiment specification."""
    lines = [
        "=" * 48,
        "STOCK_BOT PAPER EXPERIMENT",
        "=" * 48,
        "",
        f"Experiment ID       {experiment_id}",
        "",
        f"Start                {start_time}",
        f"End                  {end_time}",
        "",
        f"Trades               {metrics.total_trades}",
        f"Wins                 {metrics.wins}",
        f"Losses               {metrics.losses}",
        f"Win Rate             {metrics.win_rate_pct:.2f}%",
        "",
        f"Gross P&L            ₹{metrics.gross_pnl:,.2f}",
        f"Fees                 ₹{metrics.total_fees:,.2f}",
        f"Slippage             ₹{metrics.total_slippage:,.2f}",
        f"Net P&L              ₹{metrics.net_pnl:,.2f}",
        "",
        f"Average Win          ₹{metrics.average_win:,.2f}",
        f"Average Loss         ₹{metrics.average_loss:,.2f}",
        f"Profit Factor        {metrics.profit_factor:.2f}",
        f"Expectancy           ₹{metrics.expectancy:,.2f}",
        "",
        f"Max Drawdown         ₹{metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)",
        f"Avg Holding Time     {metrics.avg_holding_minutes:.1f} mins",
        "",
        "LONG:",
        f"  trades             {metrics.long_trades}",
        f"  wins               {metrics.long_wins}",
        f"  losses             {metrics.long_losses}",
        f"  win rate           {metrics.long_win_rate_pct:.2f}%",
        f"  net pnl            ₹{metrics.long_net_pnl:,.2f}",
        "",
        "SHORT:",
        f"  trades             {metrics.short_trades}",
        f"  wins               {metrics.short_wins}",
        f"  losses             {metrics.short_losses}",
        f"  win rate           {metrics.short_win_rate_pct:.2f}%",
        f"  net pnl            ₹{metrics.short_net_pnl:,.2f}",
        "",
    ]

    if metrics.regime_breakdown:
        lines.append("REGIME:")
        for r_name, r_data in metrics.regime_breakdown.items():
            lines.append(f"  {r_name}:")
            lines.append(f"    trades           {r_data['trades']}")
            lines.append(f"    wins             {r_data['wins']}")
            lines.append(f"    losses           {r_data['losses']}")
            lines.append(f"    net pnl          ₹{r_data['net_pnl']:,.2f}")
        lines.append("")

    if metrics.exit_reason_breakdown:
        lines.append("EXIT REASONS:")
        for reason, count in metrics.exit_reason_breakdown.items():
            lines.append(f"  {reason:<18} {count}")
        lines.append("")

    lines.extend([
        f"Model:               {model_version}",
        f"Strategy:            {strategy_version}",
        f"Risk:                {risk_version}",
        f"Data:                {feed_name} ({timeframe})",
        "",
        f"Live Broker Orders:  {live_broker_orders}",
        "=" * 48,
    ])

    return "\n".join(lines)


__all__ = [
    "PaperExperimentMetrics",
    "calculate_paper_metrics",
    "generate_experiment_report",
]
