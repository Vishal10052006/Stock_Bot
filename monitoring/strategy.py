from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True, slots=True)
class StrategyMonitoringSnapshot:
    decisions: int
    trades: int
    long_trades: int = 0
    short_trades: int = 0
    no_trade: int = 0
    wins: int = 0
    losses: int = 0
    net_pnl: float = 0.0
    def __post_init__(self) -> None:
        counters = (self.decisions, self.trades, self.long_trades, self.short_trades, self.no_trade, self.wins, self.losses)
        if any(int(v) < 0 for v in counters): raise ValueError("strategy counters must be non-negative")
        if self.trades > self.decisions or self.wins + self.losses > self.trades: raise ValueError("invalid strategy counters")
        if not math.isfinite(float(self.net_pnl)): raise ValueError("net_pnl must be finite")

def evaluate_strategy_monitoring(snapshot: StrategyMonitoringSnapshot) -> dict[str, float | int]:
    d = max(snapshot.decisions, 1)
    t = snapshot.trades
    return {"decisions": snapshot.decisions, "trades": t, "signal_rate": t / d, "no_trade_rate": snapshot.no_trade / d, "long_rate": snapshot.long_trades / t if t else 0.0, "short_rate": snapshot.short_trades / t if t else 0.0, "win_rate": snapshot.wins / t if t else 0.0, "loss_rate": snapshot.losses / t if t else 0.0, "net_pnl": float(snapshot.net_pnl)}
