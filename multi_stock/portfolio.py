"""Observation-only portfolio context for multi-stock intelligence."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from portfolio.contracts import PortfolioPosition, PortfolioSnapshot


@dataclass(frozen=True, slots=True)
class PortfolioContext:
    """Point-in-time portfolio state exposed to multi-stock intelligence."""

    timestamp: pd.Timestamp
    equity: float
    cash: float | None
    gross_exposure: float
    net_exposure: float
    position_count: int
    positions: tuple[PortfolioPosition, ...] = ()
    authority: str = "OBSERVATION_ONLY"

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not math.isfinite(self.equity) or self.equity <= 0:
            raise ValueError("equity must be finite and positive")
        if self.cash is not None and not math.isfinite(self.cash):
            raise ValueError("cash must be finite")
        if not math.isfinite(self.gross_exposure) or self.gross_exposure < 0:
            raise ValueError("gross_exposure must be finite and non-negative")
        if not math.isfinite(self.net_exposure):
            raise ValueError("net_exposure must be finite")
        if self.position_count < 0:
            raise ValueError("position_count must be non-negative")
        positions = tuple(self.positions)
        if len(positions) != self.position_count:
            raise ValueError("position_count must match positions")
        symbols = [p.symbol for p in positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("duplicate portfolio symbols")
        object.__setattr__(self, "timestamp", timestamp)

    @property
    def gross_exposure_fraction(self) -> float:
        return self.gross_exposure / self.equity

    @property
    def net_exposure_fraction(self) -> float:
        return self.net_exposure / self.equity

    def as_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": self.equity,
            "cash": self.cash,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "gross_exposure_fraction": self.gross_exposure_fraction,
            "net_exposure_fraction": self.net_exposure_fraction,
            "position_count": self.position_count,
            "positions": tuple(
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "mark_price": p.mark_price,
                    "market_value": p.market_value,
                    "sector": p.sector,
                }
                for p in self.positions
            ),
            "authority": self.authority,
        }


def build_portfolio_context(
    timestamp: pd.Timestamp,
    snapshot: PortfolioSnapshot,
    *,
    cash: float | None = None,
) -> PortfolioContext:
    """Adapt the authoritative PortfolioSnapshot without mutation or policy."""
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    if snapshot.as_of > timestamp:
        raise ValueError("future portfolio snapshot rejected")

    positions = tuple(sorted(snapshot.positions, key=lambda p: p.symbol))
    return PortfolioContext(
        timestamp=timestamp,
        equity=float(snapshot.equity),
        cash=cash,
        gross_exposure=float(snapshot.gross_exposure),
        net_exposure=float(sum(p.market_value for p in positions)),
        position_count=len(positions),
        positions=positions,
    )
