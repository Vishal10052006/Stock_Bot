"""Deterministic broker adapter for execution-engine tests and paper mode.

This adapter intentionally performs no network I/O. It models order
acknowledgement/fills while preserving the same Execution Engine contract that a
real broker adapter must satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
import math

import pandas as pd

from execution.engine import (
    Fill,
    OrderRequest,
    OrderSide,
    OrderSnapshot,
    OrderStatus,
    PositionSnapshot,
)


@dataclass(frozen=True, slots=True)
class PaperAdapterConfig:
    """Deterministic paper assumptions."""

    slippage_bps: float = 5.0
    fee_bps: float = 2.0
    partial_fill_ratio: float = 1.0

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.slippage_bps)
            or not math.isfinite(self.fee_bps)
            or self.slippage_bps < 0
            or self.fee_bps < 0
        ):
            raise ValueError("slippage_bps and fee_bps must be finite and non-negative")
        if not 0.0 < self.partial_fill_ratio <= 1.0:
            raise ValueError("partial_fill_ratio must be in (0, 1]")


class PaperBrokerAdapter:
    """In-memory paper broker with deterministic fills."""

    def __init__(
        self,
        config: PaperAdapterConfig | None = None,
        *,
        price_provider: Callable[[OrderRequest], float] | None = None,
    ) -> None:
        self.config = config or PaperAdapterConfig()
        self.price_provider = price_provider
        self._orders: dict[str, OrderSnapshot] = {}
        self._requests: dict[str, OrderRequest] = {}
        self._positions: dict[str, PositionSnapshot] = {}
        self._sequence = 0

    def _now(self) -> pd.Timestamp:
        return pd.Timestamp(datetime.now(timezone.utc))

    def submit(self, order: OrderRequest) -> OrderSnapshot:
        if order.client_order_id in self._orders:
            return self._orders[order.client_order_id]

        self._sequence += 1
        price = (
            float(self.price_provider(order))
            if self.price_provider is not None
            else (
                float(order.limit_price)
                if order.limit_price is not None
                else 100.0
            )
        )
        if not math.isfinite(price) or price <= 0:
            raise ValueError("paper execution price must be positive and finite")

        ratio = self.config.partial_fill_ratio
        filled_quantity = order.quantity * ratio
        if ratio < 1.0:
            filled_quantity = float(int(filled_quantity))
            if filled_quantity <= 0:
                filled_quantity = min(order.quantity, 1.0)

        adverse = self.config.slippage_bps / 10_000.0
        if order.side is OrderSide.BUY:
            fill_price = price * (1.0 + adverse)
        else:
            fill_price = price * (1.0 - adverse)

        fee = fill_price * filled_quantity * self.config.fee_bps / 10_000.0
        fill = Fill(
            fill_id=f"PF-{self._sequence:08d}",
            client_order_id=order.client_order_id,
            quantity=filled_quantity,
            price=fill_price,
            fee=fee,
            timestamp=self._now(),
        )

        status = (
            OrderStatus.FILLED
            if filled_quantity >= order.quantity
            else OrderStatus.PARTIALLY_FILLED
        )
        snapshot = OrderSnapshot(
            broker_order_id=f"PAPER-{self._sequence:08d}",
            client_order_id=order.client_order_id,
            status=status,
            requested_quantity=order.quantity,
            filled_quantity=filled_quantity,
            average_fill_price=fill_price,
            reason="Deterministic paper fill.",
            updated_at=fill.timestamp,
            fills=(fill,),
        )
        self._orders[order.client_order_id] = snapshot
        self._requests[order.client_order_id] = order
        self._apply_fill(order, fill)
        return snapshot

    def fill_remaining(self, client_order_id: str, *, after_cancel: bool = False) -> OrderSnapshot:
        """Advance a paper order with its outstanding quantity.

        ``after_cancel=True`` models a broker race where cancellation loses
        to a fill that was already accepted by the broker.
        """
        prior = self._orders.get(client_order_id)
        order = self._requests.get(client_order_id)
        if prior is None or order is None:
            raise KeyError(f"paper order not found: {client_order_id}")
        allowed = {OrderStatus.PARTIALLY_FILLED}
        if after_cancel:
            allowed.add(OrderStatus.CANCELLED)
        if prior.status is OrderStatus.FILLED:
            return prior
        if prior.status not in allowed:
            raise ValueError(f"cannot complete partially filled order in state {prior.status.value}")

        remaining = prior.requested_quantity - prior.filled_quantity
        if remaining <= 0:
            return prior
        self._sequence += 1
        price = float(self.price_provider(order)) if self.price_provider is not None else (float(order.limit_price) if order.limit_price is not None else 100.0)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("paper execution price must be positive and finite")
        adverse = self.config.slippage_bps / 10_000.0
        fill_price = price * (1.0 + adverse if order.side is OrderSide.BUY else 1.0 - adverse)
        fee = fill_price * remaining * self.config.fee_bps / 10_000.0
        fill = Fill(fill_id=f"PF-{self._sequence:08d}", client_order_id=order.client_order_id, quantity=remaining, price=fill_price, fee=fee, timestamp=self._now())
        total = prior.filled_quantity + remaining
        snapshot = OrderSnapshot(
            broker_order_id=prior.broker_order_id, client_order_id=prior.client_order_id,
            status=OrderStatus.FILLED, requested_quantity=prior.requested_quantity,
            filled_quantity=total,
            average_fill_price=((prior.filled_quantity * float(prior.average_fill_price) + remaining * fill_price) / total),
            reason=("Deterministic completion after cancellation race." if after_cancel else "Deterministic completion of outstanding paper quantity."),
            updated_at=fill.timestamp, fills=prior.fills + (fill,),
        )
        self._orders[client_order_id] = snapshot
        self._apply_fill(order, fill)
        return snapshot
    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        return self._orders.get(client_order_id)

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        prior = self._orders.get(client_order_id)
        if prior is None:
            raise KeyError(f"paper order not found: {client_order_id}")
        if prior.status in {OrderStatus.FILLED, OrderStatus.CANCELLED}:
            return prior
        snapshot = OrderSnapshot(
            broker_order_id=prior.broker_order_id,
            client_order_id=prior.client_order_id,
            status=OrderStatus.CANCELLED,
            requested_quantity=prior.requested_quantity,
            filled_quantity=prior.filled_quantity,
            average_fill_price=prior.average_fill_price,
            reason="Paper order cancelled.",
            updated_at=self._now(),
            fills=prior.fills,
        )
        self._orders[client_order_id] = snapshot
        return snapshot

    def positions(self) -> tuple[PositionSnapshot, ...]:
        # Return both long and short net positions. A negative quantity
        # is a valid short position and must not be silently discarded.
        return tuple(
            position
            for position in self._positions.values()
            if position.quantity != 0
        )

    def _apply_fill(self, order: OrderRequest, fill: Fill) -> None:
        """Update a signed net position from one fill.

        Positive quantity represents LONG exposure and negative quantity
        represents SHORT exposure. Reversals close existing exposure first
        and then open the residual quantity in the new direction.
        """
        symbol = order.symbol
        current = self._positions.get(symbol)
        current_qty = current.quantity if current is not None else 0.0
        signed_fill = fill.quantity if order.side is OrderSide.BUY else -fill.quantity

        if current_qty == 0.0:
            self._positions[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=signed_fill,
                average_price=fill.price,
            )
            return

        same_direction = (current_qty > 0 and signed_fill > 0) or (
            current_qty < 0 and signed_fill < 0
        )

        if same_direction:
            new_qty = current_qty + signed_fill
            weighted_price = (
                abs(current_qty) * current.average_price
                + abs(signed_fill) * fill.price
            ) / abs(new_qty)
            self._positions[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=new_qty,
                average_price=weighted_price,
            )
            return

        # Opposite-side fill closes existing exposure first.
        close_qty = min(abs(current_qty), abs(signed_fill))
        residual = abs(signed_fill) - close_qty
        if residual > 0:
            self._positions[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=residual if signed_fill > 0 else -residual,
                average_price=fill.price,
            )
        elif abs(current_qty) == close_qty:
            self._positions.pop(symbol, None)
        else:
            self._positions[symbol] = PositionSnapshot(
                symbol=symbol,
                quantity=current_qty,
                average_price=current.average_price,
            )



__all__ = ["PaperAdapterConfig", "PaperBrokerAdapter"]