"""Transparent portfolio-risk heat measurements."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import PortfolioRiskState, RiskPolicy


@dataclass(frozen=True, slots=True)
class PortfolioHeat:
    """Component-wise risk utilization; no arbitrary composite score."""
    trade_risk_utilization: float
    gross_exposure_utilization: float
    net_exposure_utilization: float
    daily_loss_utilization: float
    drawdown_utilization: float
    open_position_utilization: float
    entry_count_utilization: float


def calculate_portfolio_heat(state: PortfolioRiskState, policy: RiskPolicy) -> PortfolioHeat:
    """Return normalized risk utilizations."""
    peak = state.peak_equity if state.peak_equity is not None else state.equity
    drawdown = max(0.0, peak - state.equity)
    return PortfolioHeat(
        trade_risk_utilization=state.open_trade_risk / max(state.equity * policy.risk_per_trade, 1e-12),
        gross_exposure_utilization=state.gross_exposure / max(state.equity * policy.max_gross_exposure, 1e-12),
        net_exposure_utilization=abs(state.net_exposure) / max(state.equity * policy.max_net_exposure, 1e-12),
        daily_loss_utilization=max(0.0, -state.daily_pnl) / max(state.starting_equity * policy.max_daily_loss, 1e-12),
        drawdown_utilization=drawdown / max(peak * policy.max_drawdown, 1e-12),
        open_position_utilization=state.open_positions / max(policy.max_open_positions, 1),
        entry_count_utilization=state.entries_today / max(policy.max_entries_per_day, 1),
    )
