"""Account/session hard risk limits.

Reference: TRADING_SPECIFICATION.md sections 9, 10 and 11.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DailyRiskState:
    """Current session-level risk counters."""

    day_start_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_today: int = 0
    open_positions: int = 0

    @property
    def daily_pnl(self) -> float:
        """Return realized plus unrealized P&L."""
        return self.realized_pnl + self.unrealized_pnl


def daily_loss_limit_reached(
    *,
    state: DailyRiskState,
    max_daily_loss: float,
) -> bool:
    """Return whether the hard daily loss boundary has been reached."""
    return state.daily_pnl <= -(state.day_start_equity * max_daily_loss)
