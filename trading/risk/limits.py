"""Pure portfolio/account risk limit checks."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import MarketRiskContext, PortfolioRiskState, RiskPolicy, RiskReasonCode


@dataclass(frozen=True, slots=True)
class LimitResult:
    """One deterministic check result."""
    passed: bool
    reason: RiskReasonCode | None = None
    message: str = ""


def check_daily_loss(state: PortfolioRiskState, policy: RiskPolicy) -> LimitResult:
    """Enforce the hard daily loss limit."""
    limit = state.starting_equity * policy.max_daily_loss
    return (
        LimitResult(False, RiskReasonCode.DAILY_LOSS_LIMIT, "daily loss limit reached")
        if -state.daily_pnl >= limit
        else LimitResult(True)
    )


def check_drawdown(state: PortfolioRiskState, policy: RiskPolicy) -> LimitResult:
    """Enforce the hard portfolio drawdown limit."""
    peak = state.peak_equity if state.peak_equity is not None else state.equity
    drawdown = max(0.0, peak - state.equity)
    return (
        LimitResult(False, RiskReasonCode.MAX_DRAWDOWN, "maximum drawdown reached")
        if peak > 0 and drawdown / peak >= policy.max_drawdown
        else LimitResult(True)
    )


def check_trade_count(state: PortfolioRiskState, policy: RiskPolicy) -> LimitResult:
    """Enforce maximum daily entries."""
    return (
        LimitResult(False, RiskReasonCode.MAX_ENTRIES_PER_DAY, "maximum daily entries reached")
        if state.entries_today >= policy.max_entries_per_day
        else LimitResult(True)
    )


def check_open_positions(state: PortfolioRiskState, policy: RiskPolicy) -> LimitResult:
    """Enforce simultaneous open positions."""
    return (
        LimitResult(False, RiskReasonCode.MAX_OPEN_POSITIONS, "maximum open positions reached")
        if state.open_positions >= policy.max_open_positions
        else LimitResult(True)
    )


def check_session(market: MarketRiskContext, policy: RiskPolicy) -> LimitResult:
    """Ensure the trade arrives inside the permitted session."""
    return (
        LimitResult(False, RiskReasonCode.SESSION_CLOSED, "market session is closed")
        if policy.require_market_open and not market.is_market_open
        else LimitResult(True)
    )


def check_spread(market: MarketRiskContext, policy: RiskPolicy) -> LimitResult:
    """Reject excessive spread when a spread value is available."""
    if policy.max_spread_bps is None or market.bid_ask_spread_bps is None:
        return LimitResult(True)
    return (
        LimitResult(False, RiskReasonCode.LIQUIDITY_TOO_LOW, "bid/ask spread exceeds limit")
        if market.bid_ask_spread_bps > policy.max_spread_bps
        else LimitResult(True)
    )


def check_liquidity(
    market: MarketRiskContext,
    proposed_notional: float,
    policy: RiskPolicy,
) -> LimitResult:
    """Limit proposed notional relative to recent market volume."""
    if market.recent_volume is None:
        if policy.allow_missing_liquidity:
            return LimitResult(True)
        return LimitResult(False, RiskReasonCode.MISSING_REQUIRED_CONTEXT, "liquidity volume is required")
    if market.recent_volume <= 0:
        return LimitResult(False, RiskReasonCode.LIQUIDITY_TOO_LOW, "recent volume is not positive")
    participation = proposed_notional / market.recent_volume
    return (
        LimitResult(False, RiskReasonCode.LIQUIDITY_TOO_LOW, "proposed notional exceeds volume participation limit")
        if participation > policy.max_liquidity_participation
        else LimitResult(True)
    )
