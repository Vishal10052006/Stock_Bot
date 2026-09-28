"""Decision-time portfolio state supplied to the Phase-21 Risk Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class LiveRiskState:
    """Explicit account/portfolio state; no hidden global state is permitted."""

    available_equity: float
    day_start_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: int = 0
    trades_today: int = 0
    gross_exposure: float = 0.0
    symbol_already_open: bool = False
    liquidity_available: bool = True
    kill_switch_active: bool = False
    available_cash: float | None = None
    peak_equity: float | None = None
    sector: str | None = None
    symbol_exposure: Mapping[str, float] = field(default_factory=dict)
    sector_exposure: Mapping[str, float] = field(default_factory=dict)
    pairwise_correlation: Mapping[str, float] = field(default_factory=dict)
    atr: float | None = None
    high_volatility: bool = False
    market_data_valid: bool = True
    system_ready: bool = True

    def __post_init__(self) -> None:
        if self.available_equity <= 0:
            raise ValueError("available_equity must be positive")
        if self.day_start_equity <= 0:
            raise ValueError("day_start_equity must be positive")
        if self.open_positions < 0:
            raise ValueError("open_positions must be non-negative")
        if self.trades_today < 0:
            raise ValueError("trades_today must be non-negative")
        if self.gross_exposure < 0:
            raise ValueError("gross_exposure must be non-negative")
        if self.available_cash is not None and self.available_cash < 0:
            raise ValueError("available_cash must be non-negative")
