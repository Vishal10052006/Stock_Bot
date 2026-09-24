from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class RiskMonitoringSnapshot:
    equity: float
    daily_pnl: float
    open_positions: int
    gross_exposure: float
    daily_loss_limit: float
    max_open_positions: int
    max_gross_exposure: float
    risk_per_trade: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    def __post_init__(self) -> None:
        for name in ("equity", "daily_pnl", "gross_exposure", "daily_loss_limit", "max_gross_exposure", "risk_per_trade", "realized_pnl", "unrealized_pnl"):
            if not math.isfinite(float(getattr(self, name))): raise ValueError(f"{name} must be finite")
        if self.equity <= 0 or self.daily_loss_limit <= 0 or self.max_gross_exposure <= 0 or self.max_open_positions <= 0 or self.open_positions < 0:
            raise ValueError("invalid risk state")
        if self.risk_per_trade < 0: raise ValueError("risk_per_trade must be non-negative")

def evaluate_risk_monitoring(snapshot: RiskMonitoringSnapshot) -> tuple[dict[str, float | int], tuple[str, ...]]:
    """Report risk utilization only; Risk Engine keeps veto authority."""
    exposure_limit = snapshot.equity * snapshot.max_gross_exposure
    daily_loss_used = max(0.0, -snapshot.daily_pnl)
    breaches: list[str] = []
    if snapshot.daily_pnl <= -snapshot.daily_loss_limit: breaches.append("DAILY_LOSS_LIMIT_REACHED")
    if snapshot.open_positions >= snapshot.max_open_positions: breaches.append("MAX_OPEN_POSITIONS_REACHED")
    if snapshot.gross_exposure >= exposure_limit: breaches.append("MAX_GROSS_EXPOSURE_REACHED")
    return ({"equity": snapshot.equity, "daily_pnl": snapshot.daily_pnl, "daily_loss_used": daily_loss_used, "open_positions": snapshot.open_positions, "gross_exposure": snapshot.gross_exposure, "exposure_utilization": snapshot.gross_exposure / exposure_limit, "position_utilization": snapshot.open_positions / snapshot.max_open_positions, "risk_per_trade": snapshot.risk_per_trade, "realized_pnl": snapshot.realized_pnl, "unrealized_pnl": snapshot.unrealized_pnl}, tuple(breaches))
