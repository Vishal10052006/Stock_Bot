"""AB-34 deterministic paper-trading runtime.

Converts an approved ExecutionAuthorization into a simulated paper order,
applies configurable slippage/fees, maintains position state, and journals
fills. No broker/network calls are made.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from trading.strategy.models import StrategyDirection


class PaperOrderStatus(str, Enum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class PaperTradingConfig:
    """Deterministic paper execution costs."""

    slippage_bps: float = 5.0
    fee_bps: float = 2.0

    def __post_init__(self) -> None:
        if self.slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError("slippage_bps and fee_bps must be non-negative")


@dataclass(frozen=True, slots=True)
class PaperOrder:
    """Immutable paper order intent/result."""

    timestamp: pd.Timestamp
    symbol: str
    direction: StrategyDirection
    requested_price: float
    fill_price: float
    quantity: float
    status: PaperOrderStatus
    fees: float
    slippage_cost: float
    reason: str

    def __post_init__(self) -> None:
        if pd.Timestamp(self.timestamp).tzinfo is None:
            raise ValueError("paper order timestamp must be timezone-aware")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.requested_price <= 0 or self.fill_price <= 0:
            raise ValueError("prices must be positive")


@dataclass(frozen=True, slots=True)
class PaperPosition:
    """Current single-symbol paper position state."""

    symbol: str
    quantity: float
    average_price: float
    realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("position quantity cannot be negative")
        if self.quantity > 0 and self.average_price <= 0:
            raise ValueError("average_price must be positive for open positions")


class PaperTradingRuntime:
    """Stateful deterministic paper runtime for one symbol."""

    def __init__(
        self,
        *,
        config: PaperTradingConfig | None = None,
    ) -> None:
        self.config = config or PaperTradingConfig()
        self._positions: dict[str, PaperPosition] = {}
        self._journal: list[PaperOrder] = []

    @property
    def journal(self) -> tuple[PaperOrder, ...]:
        """Return immutable trade journal snapshot."""
        return tuple(self._journal)

    def position(self, symbol: str) -> PaperPosition | None:
        """Return current position for a symbol."""
        return self._positions.get(symbol.upper())

    def submit(
        self,
        authorization: ExecutionAuthorization,
        *,
        price: float,
        quantity: float,
    ) -> PaperOrder:
        """Simulate a fill only when ExecutionAuthorization is approved."""
        if not isinstance(authorization, ExecutionAuthorization):
            raise TypeError("authorization must be an ExecutionAuthorization")
        if price <= 0 or quantity <= 0:
            raise ValueError("price and quantity must be positive")

        symbol = authorization.symbol.upper()

        if authorization.status is not ExecutionAuthorizationStatus.AUTHORIZED:
            order = PaperOrder(
                timestamp=authorization.timestamp,
                symbol=symbol,
                direction=authorization.direction,
                requested_price=price,
                fill_price=price,
                quantity=quantity,
                status=PaperOrderStatus.REJECTED,
                fees=0.0,
                slippage_cost=0.0,
                reason="Paper order blocked because authorization is not approved.",
            )
            self._journal.append(order)
            return order

        direction_sign = (
            1.0 if authorization.direction is StrategyDirection.LONG else -1.0
        )
        slippage_rate = self.config.slippage_bps / 10_000.0
        fill_price = price * (1.0 + direction_sign * slippage_rate)

        notional = fill_price * quantity
        fees = notional * self.config.fee_bps / 10_000.0
        slippage_cost = abs(fill_price - price) * quantity

        current = self._positions.get(symbol)
        if current is None:
            position = PaperPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=fill_price,
            )
        else:
            if direction_sign > 0:
                new_quantity = current.quantity + quantity
                weighted_price = (
                    current.average_price * current.quantity
                    + fill_price * quantity
                ) / new_quantity
                position = PaperPosition(
                    symbol=symbol,
                    quantity=new_quantity,
                    average_price=weighted_price,
                    realized_pnl=current.realized_pnl,
                )
            else:
                close_quantity = min(quantity, current.quantity)
                realized = (
                    fill_price - current.average_price
                ) * close_quantity
                remaining = current.quantity - close_quantity
                position = PaperPosition(
                    symbol=symbol,
                    quantity=remaining,
                    average_price=current.average_price if remaining else 0.0,
                    realized_pnl=current.realized_pnl + realized - fees,
                )

        self._positions[symbol] = position

        order = PaperOrder(
            timestamp=authorization.timestamp,
            symbol=symbol,
            direction=authorization.direction,
            requested_price=price,
            fill_price=fill_price,
            quantity=quantity,
            status=PaperOrderStatus.FILLED,
            fees=fees,
            slippage_cost=slippage_cost,
            reason="Paper fill simulated deterministically.",
        )
        self._journal.append(order)
        return order

    def mark_to_market(self, symbol: str, price: float) -> float:
        """Return unrealized + realized PnL for the current paper position."""
        symbol = symbol.upper()
        position = self._positions.get(symbol)
        if position is None:
            return 0.0
        if price <= 0:
            raise ValueError("mark price must be positive")
        unrealized = (price - position.average_price) * position.quantity
        return position.realized_pnl + unrealized
