"""Production-grade broker-neutral execution engine for STOCK_BOT.

Execution sits strictly downstream of deterministic Risk and independent
Safety. It consumes an approved ExecutionAuthorization, creates one immutable
OrderRequest, submits through a broker adapter, tracks lifecycle transitions,
records fills, and reconciles local state.

References:
- TRADING_SPECIFICATION.md
- docs/PHASE_11_DIRECT_BUILD.md
- docs/FINAL_SYSTEM_AUDIT.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Mapping, Protocol

import pandas as pd

from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from trading.strategy.models import StrategyDirection


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class TimeInForce(str, Enum):
    DAY = "DAY"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    REJECTED_LOCAL = "REJECTED_LOCAL"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED_BROKER = "REJECTED_BROKER"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class OrderRequest:
    """Immutable order request produced only after risk authorization."""

    client_order_id: str
    decision_id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    created_at: pd.Timestamp = field(default_factory=lambda: pd.Timestamp.now(tz="Asia/Kolkata"))
    authorization: ExecutionAuthorization | None = None

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.created_at)
        if ts.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if not self.client_order_id.strip():
            raise ValueError("client_order_id must not be empty")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type is OrderType.LIMIT and (self.limit_price is None or self.limit_price <= 0):
            raise ValueError("LIMIT orders require a positive limit_price")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise ValueError("MARKET orders must not define limit_price")
        object.__setattr__(self, "created_at", ts)
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True, slots=True)
class Fill:
    """Immutable broker fill."""

    fill_id: str
    client_order_id: str
    quantity: float
    price: float
    fee: float = 0.0
    timestamp: pd.Timestamp = field(default_factory=lambda: pd.Timestamp.now(tz="Asia/Kolkata"))

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("fill timestamp must be timezone-aware")
        if not self.fill_id.strip() or not self.client_order_id.strip():
            raise ValueError("fill identifiers must not be empty")
        if self.quantity <= 0 or self.price <= 0:
            raise ValueError("fill quantity and price must be positive")
        if self.fee < 0:
            raise ValueError("fill fee must be non-negative")
        object.__setattr__(self, "timestamp", ts)


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    """Immutable point-in-time order state returned by an adapter."""

    broker_order_id: str
    client_order_id: str
    status: OrderStatus
    requested_quantity: float
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    reason: str = ""
    updated_at: pd.Timestamp = field(default_factory=lambda: pd.Timestamp.now(tz="Asia/Kolkata"))
    fills: tuple[Fill, ...] = ()

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.updated_at)
        if ts.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        if not self.broker_order_id.strip() or not self.client_order_id.strip():
            raise ValueError("order identifiers must not be empty")
        if self.requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive")
        if self.filled_quantity < 0 or self.filled_quantity > self.requested_quantity + 1e-12:
            raise ValueError("filled_quantity must be within requested quantity")
        if self.average_fill_price is not None and self.average_fill_price <= 0:
            raise ValueError("average_fill_price must be positive")
        object.__setattr__(self, "updated_at", ts)
        object.__setattr__(self, "fills", tuple(self.fills))


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    """Immutable position state used for reconciliation."""

    symbol: str
    quantity: float
    average_price: float

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if self.quantity < 0 or self.average_price < 0:
            raise ValueError("position values must be non-negative")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Auditable terminal or intermediate execution result."""

    request: OrderRequest
    snapshot: OrderSnapshot
    accepted: bool
    latency_ms: float
    error: str | None = None

    @property
    def filled(self) -> bool:
        return self.snapshot.status is OrderStatus.FILLED

    @property
    def fingerprint(self) -> str:
        payload = {
            "client_order_id": self.request.client_order_id,
            "decision_id": self.request.decision_id,
            "symbol": self.request.symbol,
            "quantity": self.request.quantity,
            "status": self.snapshot.status.value,
            "filled_quantity": self.snapshot.filled_quantity,
            "average_fill_price": self.snapshot.average_fill_price,
            "error": self.error,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class BrokerAdapter(Protocol):
    """Minimal broker contract; broker-specific details stay outside execution."""

    def submit(self, order: OrderRequest) -> OrderSnapshot:
        ...

    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        ...

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        ...

    def positions(self) -> tuple[PositionSnapshot, ...]:
        ...


class OrderStateMachine:
    """Strict lifecycle transition validator."""

    _ALLOWED = {
        OrderStatus.CREATED: {OrderStatus.VALIDATED, OrderStatus.REJECTED_LOCAL},
        OrderStatus.VALIDATED: {OrderStatus.SUBMITTING, OrderStatus.REJECTED_LOCAL},
        OrderStatus.SUBMITTING: {
            OrderStatus.SUBMITTED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.FAILED,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.SUBMITTED: {
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.OPEN: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.PARTIALLY_FILLED: {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.UNKNOWN,
        },
        OrderStatus.CANCEL_PENDING: {OrderStatus.CANCELLED, OrderStatus.FILLED, OrderStatus.UNKNOWN},
        OrderStatus.UNKNOWN: {
            OrderStatus.SUBMITTED,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED_BROKER,
            OrderStatus.FAILED,
        },
    }

    @classmethod
    def transition(cls, current: OrderStatus, target: OrderStatus) -> OrderStatus:
        if target not in cls._ALLOWED.get(current, set()):
            raise ValueError(f"invalid order transition: {current.value} -> {target.value}")
        return target


class ExecutionEngine:
    """Execute risk-approved orders through a broker-neutral adapter."""

    VERSION = "EXEC-v1.0"

    def __init__(self, adapter: BrokerAdapter) -> None:
        self.adapter = adapter
        self._orders: dict[str, OrderSnapshot] = {}
        self._fills: dict[str, tuple[Fill, ...]] = {}

    @staticmethod
    def side_for_direction(direction: StrategyDirection) -> OrderSide:
        if direction is StrategyDirection.LONG:
            return OrderSide.BUY
        if direction is StrategyDirection.SHORT:
            return OrderSide.SELL
        raise ValueError("NO_TRADE cannot be executed")

    @classmethod
    def from_authorization(
        cls,
        authorization: ExecutionAuthorization,
        *,
        decision_id: str,
        order_type: OrderType = OrderType.MARKET,
        limit_price: float | None = None,
        created_at: pd.Timestamp | None = None,
    ) -> OrderRequest:
        """Convert an approved authorization into an immutable order request."""
        if not isinstance(authorization, ExecutionAuthorization):
            raise TypeError("authorization must be an ExecutionAuthorization")
        if authorization.status is not ExecutionAuthorizationStatus.AUTHORIZED:
            raise ValueError("execution requires AUTHORIZED risk/safety control")
        if authorization.approved_quantity <= 0:
            raise ValueError("authorized quantity must be positive")
        if not decision_id.strip():
            raise ValueError("decision_id must not be empty")

        timestamp = pd.Timestamp(created_at or authorization.timestamp)
        # The client order id is deterministic for one decision + risk version.
        raw = f"{decision_id}|{authorization.symbol}|{authorization.direction.value}|{authorization.risk_version}"
        client_order_id = "SB-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

        return OrderRequest(
            client_order_id=client_order_id,
            decision_id=decision_id,
            symbol=authorization.symbol,
            side=cls.side_for_direction(authorization.direction),
            quantity=float(authorization.approved_quantity),
            order_type=order_type,
            limit_price=limit_price,
            created_at=timestamp,
            authorization=authorization,
        )

    def validate(self, order: OrderRequest) -> None:
        """Perform execution-local checks without changing risk sizing."""
        if not isinstance(order, OrderRequest):
            raise TypeError("order must be an OrderRequest")
        if order.authorization is None:
            raise ValueError("order must retain risk/safety authorization")
        if order.authorization.status is not ExecutionAuthorizationStatus.AUTHORIZED:
            raise ValueError("order authorization is not active")
        if order.quantity != order.authorization.approved_quantity:
            raise ValueError("execution quantity must exactly equal risk-approved quantity")
        if order.symbol != order.authorization.symbol:
            raise ValueError("execution symbol does not match authorization")
        if order.side != self.side_for_direction(order.authorization.direction):
            raise ValueError("execution side does not match authorization")
        if order.quantity <= 0:
            raise ValueError("execution quantity must be positive")

    def submit(self, order: OrderRequest) -> ExecutionResult:
        """Validate, submit once, record broker acknowledgement, and return result.

        Unknown submission responses are fail-closed. The engine reconciles via
        get_order before any retry is permitted.
        """
        self.validate(order)

        existing = self._orders.get(order.client_order_id)
        if existing is not None:
            # Idempotent repeat: never create a second order for the same key.
            return ExecutionResult(
                request=order,
                snapshot=existing,
                accepted=existing.status not in {
                    OrderStatus.REJECTED_LOCAL,
                    OrderStatus.REJECTED_BROKER,
                    OrderStatus.FAILED,
                },
                latency_ms=0.0,
            )

        start = time.perf_counter()
        try:
            snapshot = self.adapter.submit(order)
        except Exception as exc:  # pragma: no cover - adapter implementation specific.
            snapshot = OrderSnapshot(
                broker_order_id=f"UNKNOWN:{order.client_order_id}",
                client_order_id=order.client_order_id,
                status=OrderStatus.UNKNOWN,
                requested_quantity=order.quantity,
                reason=f"broker submission exception: {exc}",
            )
            latency_ms = (time.perf_counter() - start) * 1000.0
            self._orders[order.client_order_id] = snapshot
            return ExecutionResult(
                request=order,
                snapshot=snapshot,
                accepted=False,
                latency_ms=latency_ms,
                error=str(exc),
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        if snapshot.client_order_id != order.client_order_id:
            raise ValueError("broker response client_order_id mismatch")
        if snapshot.requested_quantity != order.quantity:
            raise ValueError("broker response quantity mismatch")

        self._orders[order.client_order_id] = snapshot
        self._fills[order.client_order_id] = tuple(snapshot.fills)
        return ExecutionResult(
            request=order,
            snapshot=snapshot,
            accepted=snapshot.status not in {
                OrderStatus.REJECTED_BROKER,
                OrderStatus.FAILED,
            },
            latency_ms=latency_ms,
            error=snapshot.reason or None,
        )

    def refresh(self, client_order_id: str) -> OrderSnapshot:
        """Fetch authoritative broker state and merge it into the local journal."""
        if not client_order_id.strip():
            raise ValueError("client_order_id must not be empty")
        snapshot = self.adapter.get_order(client_order_id)
        if snapshot is None:
            prior = self._orders.get(client_order_id)
            if prior is None:
                raise KeyError(f"order not found: {client_order_id}")
            unknown = OrderSnapshot(
                broker_order_id=prior.broker_order_id,
                client_order_id=prior.client_order_id,
                status=OrderStatus.UNKNOWN,
                requested_quantity=prior.requested_quantity,
                filled_quantity=prior.filled_quantity,
                average_fill_price=prior.average_fill_price,
                reason="broker returned no order state",
                fills=prior.fills,
            )
            self._orders[client_order_id] = unknown
            return unknown

        self._orders[client_order_id] = snapshot
        self._fills[client_order_id] = tuple(snapshot.fills)
        return snapshot

    def reconcile_order(self, client_order_id: str) -> bool:
        """Return True only when local and broker order state agree."""
        local = self._orders.get(client_order_id)
        broker = self.adapter.get_order(client_order_id)
        if local is None or broker is None:
            return False
        return (
            local.status is broker.status
            and abs(local.filled_quantity - broker.filled_quantity) <= 1e-12
            and local.average_fill_price == broker.average_fill_price
        )

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        """Cancel one known order and store the authoritative broker state."""
        prior = self._orders.get(client_order_id)
        if prior is None:
            raise KeyError(f"unknown local order: {client_order_id}")
        if prior.status in {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED_BROKER}:
            raise ValueError(f"cannot cancel order in state {prior.status.value}")

        snapshot = self.adapter.cancel(client_order_id)
        self._orders[client_order_id] = snapshot
        self._fills[client_order_id] = tuple(snapshot.fills)
        return snapshot

    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        return self._orders.get(client_order_id)

    def fills(self, client_order_id: str) -> tuple[Fill, ...]:
        return self._fills.get(client_order_id, ())

    def open_orders(self) -> tuple[OrderSnapshot, ...]:
        return tuple(
            snapshot
            for snapshot in self._orders.values()
            if snapshot.status in {
                OrderStatus.SUBMITTED,
                OrderStatus.OPEN,
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.CANCEL_PENDING,
                OrderStatus.UNKNOWN,
            }
        )

    @property
    def journal(self) -> tuple[OrderSnapshot, ...]:
        return tuple(self._orders.values())

    def reconcile_positions(self, local: tuple[PositionSnapshot, ...]) -> bool:
        """Compare local positions with the authoritative broker snapshot."""
        broker = self.adapter.positions()
        local_map = {item.symbol: (item.quantity, item.average_price) for item in local}
        broker_map = {item.symbol: (item.quantity, item.average_price) for item in broker}
        return local_map == broker_map


class ExecutionReadiness:
    """Read-only execution readiness checks; never enables live trading."""

    def __init__(self, *, live_locked: bool = True) -> None:
        self.live_locked = live_locked

    def check(self, *, risk_authorized: bool, safety_allowed: bool) -> bool:
        if self.live_locked:
            return False
        return risk_authorized and safety_allowed


__all__ = [
    "BrokerAdapter",
    "ExecutionEngine",
    "ExecutionReadiness",
    "ExecutionResult",
    "Fill",
    "OrderRequest",
    "OrderSide",
    "OrderSnapshot",
    "OrderStatus",
    "OrderStateMachine",
    "OrderType",
    "PositionSnapshot",
    "TimeInForce",
]
