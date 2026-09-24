"""Immutable contracts for the portfolio management boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from portfolio.transition import PositionTransition
import hashlib
import json
import math

import pandas as pd


class PortfolioAction(str, Enum):
    """Portfolio-level disposition of a proposed trade."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """Signed portfolio position.

    Positive quantity is long; negative quantity is short.
    """

    symbol: str
    quantity: float
    mark_price: float
    sector: str | None = None

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not math.isfinite(self.quantity):
            raise ValueError("quantity must be finite")
        if not math.isfinite(self.mark_price) or self.mark_price <= 0:
            raise ValueError("mark_price must be finite and positive")
        sector = self.sector.strip() if self.sector else None
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "sector", sector)

    @property
    def market_value(self) -> float:
        """Return signed market value."""
        return self.quantity * self.mark_price


@dataclass(frozen=True, slots=True)
class TradeIntent:
    """Proposed portfolio change, not a risk authorization."""

    symbol: str
    quantity: float
    price: float
    side: str
    sector: str | None = None
    decision_id: str = ""

    def __post_init__(self) -> None:
        symbol = self.symbol.strip().upper()
        side = self.side.strip().upper()
        if not symbol:
            raise ValueError("symbol must not be empty")
        if not math.isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be finite and positive")
        if not math.isfinite(self.price) or self.price <= 0:
            raise ValueError("price must be finite and positive")
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        sector = self.sector.strip() if self.sector else None
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "sector", sector)


@dataclass(frozen=True, slots=True)
class PortfolioLimits:
    """Explicit portfolio policy.

    None means the policy is not frozen/enabled. The manager never invents
    production limits for unspecified policies.
    """

    max_positions: int | None = None
    max_gross_exposure_fraction: float | None = None
    max_symbol_exposure_fraction: float | None = None
    max_sector_exposure_fraction: float | None = None

    def __post_init__(self) -> None:
        if self.max_positions is not None and self.max_positions <= 0:
            raise ValueError("max_positions must be positive")
        for name in (
            "max_gross_exposure_fraction",
            "max_symbol_exposure_fraction",
            "max_sector_exposure_fraction",
        ):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0 or value > 1):
                raise ValueError(f"{name} must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Decision-time aggregate portfolio state."""

    as_of: pd.Timestamp
    equity: float
    positions: tuple[PortfolioPosition, ...] = ()

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.as_of)
        if timestamp.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if not math.isfinite(self.equity) or self.equity <= 0:
            raise ValueError("equity must be finite and positive")
        positions = tuple(self.positions)
        symbols = [position.symbol for position in positions]
        if len(symbols) != len(set(symbols)):
            raise ValueError("PortfolioSnapshot cannot contain duplicate symbols")
        object.__setattr__(self, "as_of", timestamp)
        object.__setattr__(self, "positions", positions)

    @property
    def gross_exposure(self) -> float:
        """Return absolute gross market value."""
        return sum(abs(position.market_value) for position in self.positions)

    @property
    def gross_exposure_fraction(self) -> float:
        """Return gross exposure divided by equity."""
        return self.gross_exposure / self.equity


@dataclass(frozen=True, slots=True)
class PortfolioDecision:
    """Immutable portfolio evaluation result."""

    action: PortfolioAction
    symbol: str
    decision_id: str
    reason_code: str
    reason: str
    current_gross_exposure_fraction: float
    projected_gross_exposure_fraction: float
    projected_position_count: int
    position_transition: PositionTransition
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        payload = {
            "action": self.action.value,
            "symbol": self.symbol,
            "decision_id": self.decision_id,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "current_gross_exposure_fraction": self.current_gross_exposure_fraction,
            "projected_gross_exposure_fraction": self.projected_gross_exposure_fraction,
            "projected_position_count": self.projected_position_count,
            "position_transition": self.position_transition.value,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        object.__setattr__(
            self,
            "fingerprint",
            hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
