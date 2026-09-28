"""Provider-neutral account and portfolio snapshot contract.

This module is observation-only. It does not place orders and does not grant
broker execution authority. Risk consumes a validated snapshot at decision
time; broker-specific adapters belong behind a separate integration boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    """Immutable point-in-time account state for risk evaluation."""

    timestamp: datetime
    equity: float
    available_cash: float
    gross_exposure: float = 0.0
    open_positions: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_today: int = 0
    source: str = "paper"

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("account snapshot timestamp must be timezone-aware")

        for name, value in (
            ("equity", self.equity),
            ("available_cash", self.available_cash),
            ("gross_exposure", self.gross_exposure),
            ("realized_pnl", self.realized_pnl),
            ("unrealized_pnl", self.unrealized_pnl),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

        if self.equity <= 0:
            raise ValueError("equity must be positive")
        if self.available_cash < 0:
            raise ValueError("available_cash must be non-negative")
        if self.gross_exposure < 0:
            raise ValueError("gross_exposure must be non-negative")
        if self.open_positions < 0:
            raise ValueError("open_positions must be non-negative")
        if self.trades_today < 0:
            raise ValueError("trades_today must be non-negative")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")

        object.__setattr__(self, "source", self.source.strip().lower())

    @property
    def net_pnl(self) -> float:
        """Return realized plus unrealized PnL."""
        return self.realized_pnl + self.unrealized_pnl

    def evidence(self) -> dict[str, object]:
        """Return deterministic non-secret account evidence."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.equity,
            "available_cash": self.available_cash,
            "gross_exposure": self.gross_exposure,
            "open_positions": self.open_positions,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "trades_today": self.trades_today,
            "source": self.source,
            "live_broker_order_submission": False,
        }


__all__ = ["AccountSnapshot"]
