"""AB-36 paper trade lifecycle and outcome capture.

Keeps trade outcome accounting separate from the execution runtime.  The
lifecycle consumes already-filled paper orders and causal market marks; it
does not place orders or modify risk authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd

from paper.runtime import PaperOrder, PaperOrderStatus
from trading.strategy.models import StrategyDirection


class TradeLifecycleStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class TradeOutcome:
    """Immutable outcome record for one completed paper trade."""

    symbol: str
    direction: StrategyDirection
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float
    holding_minutes: float
    mae: float
    mfe: float
    status: TradeLifecycleStatus = TradeLifecycleStatus.CLOSED

    def __post_init__(self) -> None:
        if self.entry_time.tzinfo is None or self.exit_time.tzinfo is None:
            raise ValueError("trade timestamps must be timezone-aware")
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time must not precede entry_time")
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("trade prices must be positive")
        if self.quantity <= 0:
            raise ValueError("trade quantity must be positive")
        if self.mae > 0 or self.mfe < 0:
            raise ValueError("MAE must be <= 0 and MFE must be >= 0")


class PaperTradeLifecycle:
    """Track one open trade per symbol and close it into an outcome record."""

    def __init__(self) -> None:
        self._open: dict[str, dict[str, object]] = {}
        self._outcomes: list[TradeOutcome] = []

    @property
    def outcomes(self) -> tuple[TradeOutcome, ...]:
        """Return completed outcomes in chronological close order."""
        return tuple(self._outcomes)

    def open(self, order: PaperOrder) -> None:
        """Open a lifecycle record from a filled paper order."""
        if not isinstance(order, PaperOrder):
            raise TypeError("order must be a PaperOrder")
        if order.status is not PaperOrderStatus.FILLED:
            raise ValueError("only FILLED paper orders can open a trade")

        symbol = order.symbol.upper()
        if symbol in self._open:
            raise ValueError(f"trade already open for {symbol}")

        self._open[symbol] = {
            "order": order,
            "quantity": order.quantity,
            "entry_fees": order.fees,
            "entry_slippage_cost": order.slippage_cost,
            "mae": 0.0,
            "mfe": 0.0,
        }

    def mark(self, symbol: str, *, timestamp: pd.Timestamp, price: float) -> None:
        """Update MAE/MFE using a causal market price mark."""
        symbol = symbol.upper()
        if symbol not in self._open:
            raise KeyError(f"no open trade for {symbol}")
        if price <= 0:
            raise ValueError("mark price must be positive")

        timestamp = pd.Timestamp(timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("mark timestamp must be timezone-aware")

        record = self._open[symbol]
        order = record["order"]
        assert isinstance(order, PaperOrder)
        quantity = float(record["quantity"])
        if timestamp < order.timestamp:
            raise ValueError("mark timestamp must not precede entry")

        signed_move = (
            price - order.fill_price
            if order.direction is StrategyDirection.LONG
            else order.fill_price - price
        )
        record["mae"] = min(float(record["mae"]), signed_move * quantity)
        record["mfe"] = max(float(record["mfe"]), signed_move * quantity)

    def close_partial(
        self,
        symbol: str,
        *,
        timestamp: pd.Timestamp,
        price: float,
        quantity: float,
        exit_fees: float = 0.0,
        exit_slippage_cost: float = 0.0,
    ) -> TradeOutcome:
        """Close part or all of an open trade without losing lifecycle state."""
        symbol = symbol.upper()
        if symbol not in self._open:
            raise KeyError(f"no open trade for {symbol}")
        if price <= 0 or quantity <= 0:
            raise ValueError("price and quantity must be positive")
        if exit_fees < 0 or exit_slippage_cost < 0:
            raise ValueError("exit costs must be non-negative")

        timestamp = pd.Timestamp(timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("exit timestamp must be timezone-aware")

        record = self._open[symbol]
        order = record["order"]
        assert isinstance(order, PaperOrder)
        current_quantity = float(record["quantity"])
        if quantity > current_quantity + 1e-12:
            raise ValueError("partial close quantity exceeds open quantity")
        if timestamp < order.timestamp:
            raise ValueError("exit timestamp must not precede entry")

        signed_unit_pnl = (
            price - order.fill_price
            if order.direction is StrategyDirection.LONG
            else order.fill_price - price
        )
        gross_pnl = signed_unit_pnl * quantity
        entry_fee_share = float(record["entry_fees"]) * quantity / current_quantity
        entry_slippage_share = float(record["entry_slippage_cost"]) * quantity / current_quantity

        outcome = TradeOutcome(
            symbol=symbol,
            direction=order.direction,
            entry_time=order.timestamp,
            exit_time=timestamp,
            entry_price=order.fill_price,
            exit_price=price,
            quantity=quantity,
            gross_pnl=gross_pnl,
            fees=entry_fee_share + exit_fees,
            slippage_cost=entry_slippage_share + exit_slippage_cost,
            net_pnl=gross_pnl - entry_fee_share - exit_fees,
            holding_minutes=(timestamp - order.timestamp).total_seconds() / 60.0,
            mae=float(record["mae"]),
            mfe=float(record["mfe"]),
        )
        self._outcomes.append(outcome)

        remaining = current_quantity - quantity
        if remaining <= 1e-12:
            self._open.pop(symbol)
        else:
            record["quantity"] = remaining
            record["entry_fees"] = float(record["entry_fees"]) - entry_fee_share
            record["entry_slippage_cost"] = float(record["entry_slippage_cost"]) - entry_slippage_share
            record["mae"] = 0.0
            record["mfe"] = 0.0

        return outcome

    def close(
        self,
        symbol: str,
        *,
        timestamp: pd.Timestamp,
        price: float,
        exit_fees: float = 0.0,
        exit_slippage_cost: float = 0.0,
    ) -> TradeOutcome:
        """Close an open trade and create its immutable outcome record."""
        symbol = symbol.upper()
        if symbol not in self._open:
            raise KeyError(f"no open trade for {symbol}")
        if price <= 0:
            raise ValueError("exit price must be positive")
        if exit_fees < 0:
            raise ValueError("exit_fees must be non-negative")
        if exit_slippage_cost < 0:
            raise ValueError("exit_slippage_cost must be non-negative")

        timestamp = pd.Timestamp(timestamp)
        if timestamp.tzinfo is None:
            raise ValueError("exit timestamp must be timezone-aware")

        record = self._open[symbol]
        order = record["order"]
        assert isinstance(order, PaperOrder)

        return self.close_partial(
            symbol,
            timestamp=timestamp,
            price=price,
            quantity=float(record["quantity"]),
            exit_fees=exit_fees,
            exit_slippage_cost=exit_slippage_cost,
        )
