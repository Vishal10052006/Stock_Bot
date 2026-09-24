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
import math
import json
import time
from typing import Protocol

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
        if not math.isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("quantity must be positive and finite")
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
        if not math.isfinite(self.quantity) or not math.isfinite(self.price) or self.quantity <= 0 or self.price <= 0:
            raise ValueError("fill quantity and price must be positive and finite")
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
        if not math.isfinite(self.requested_quantity) or self.requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive and finite")
        if self.filled_quantity < 0 or self.filled_quantity > self.requested_quantity + 1e-12:
            raise ValueError("filled_quantity must be within requested quantity")
        if self.average_fill_price is not None and (not math.isfinite(self.average_fill_price) or self.average_fill_price <= 0):
            raise ValueError("average_fill_price must be positive and finite")
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
        if not math.isfinite(self.quantity):
            raise ValueError("quantity must be finite")
        if not math.isfinite(self.average_price) or self.average_price < 0:
            raise ValueError("average_price must be non-negative and finite")
        # Signed quantity: positive=long, negative=short. This is required
        # because NSE research/paper trading supports both directions.
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


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    """Immutable lifecycle event retained for audit and execution metrics."""

    client_order_id: str
    from_status: OrderStatus | None
    to_status: OrderStatus
    timestamp: pd.Timestamp
    reason: str = ""

    def __post_init__(self) -> None:
        ts = pd.Timestamp(self.timestamp)
        if ts.tzinfo is None:
            raise ValueError("execution event timestamp must be timezone-aware")
        object.__setattr__(self, "timestamp", ts)


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Aggregate execution-quality metrics derived from observed orders."""

    orders: int
    accepted_orders: int
    filled_orders: int
    partially_filled_orders: int
    rejected_orders: int
    unknown_orders: int
    requested_quantity: float
    filled_quantity: float
    total_fees: float
    average_latency_ms: float
    fill_ratio: float
    rejection_rate: float


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
        # Simulated brokers may return immediate terminal states; real
        # brokers may acknowledge first and transition later via refresh().
        OrderStatus.SUBMITTING: {
            OrderStatus.SUBMITTED,
            OrderStatus.OPEN,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
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
        # A broker can report FILLED after local cancellation if the fill raced
        # the cancellation request. Authoritative refresh wins.
        OrderStatus.CANCELLED: {OrderStatus.FILLED, OrderStatus.UNKNOWN},
        # UNKNOWN is intentionally recoverable in both directions:
        # broker state can disappear after a terminal local observation, and
        # an unavailable broker can later return an authoritative state.
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
        OrderStatus.FILLED: {OrderStatus.UNKNOWN},
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
        self._states: dict[str, OrderStatus] = {}
        self._events: list[ExecutionEvent] = []
        self._order_requests: dict[str, OrderRequest] = {}

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
        self._order_requests[order.client_order_id] = order

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

        self._transition(order.client_order_id, OrderStatus.VALIDATED, "local validation passed")
        self._transition(order.client_order_id, OrderStatus.SUBMITTING, "broker submission started")

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
            self._transition(
                order.client_order_id,
                OrderStatus.UNKNOWN,
                f"broker submission exception: {exc}",
            )
            self._orders[order.client_order_id] = snapshot
            return ExecutionResult(
                request=order,
                snapshot=snapshot,
                accepted=False,
                latency_ms=latency_ms,
                error=str(exc),
            )

        latency_ms = (time.perf_counter() - start) * 1000.0
        self._validate_broker_snapshot(order, snapshot)

        self._transition(
            order.client_order_id,
            snapshot.status,
            snapshot.reason or "broker acknowledged order",
        )
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

    @staticmethod
    def _validate_broker_snapshot(
        order: OrderRequest,
        snapshot: OrderSnapshot,
    ) -> None:
        """Validate one broker snapshot before it can affect local state."""
        if snapshot.client_order_id != order.client_order_id:
            raise ValueError("broker response client_order_id mismatch")
        if snapshot.requested_quantity != order.quantity:
            raise ValueError("broker response quantity mismatch")
        if (
            not math.isfinite(snapshot.filled_quantity)
            or snapshot.filled_quantity < 0
            or snapshot.filled_quantity > order.quantity + 1e-12
        ):
            raise ValueError("broker response filled quantity exceeds requested quantity")

        fill_total = 0.0
        seen_fill_ids: set[str] = set()
        for fill in snapshot.fills:
            if fill.client_order_id != order.client_order_id:
                raise ValueError("broker response fill client_order_id mismatch")
            if fill.fill_id in seen_fill_ids:
                raise ValueError("broker response contains duplicate fill id")
            seen_fill_ids.add(fill.fill_id)
            if (
                not math.isfinite(fill.quantity)
                or not math.isfinite(fill.price)
                or fill.quantity <= 0
                or fill.price <= 0
            ):
                raise ValueError("broker response contains invalid fill")
            fill_total += fill.quantity

        if abs(fill_total - snapshot.filled_quantity) > 1e-12:
            raise ValueError("broker response fill total does not match filled quantity")

        if snapshot.status is OrderStatus.FILLED and (
            abs(snapshot.filled_quantity - order.quantity) > 1e-12
        ):
            raise ValueError("FILLED broker response must fill the requested quantity")

        if snapshot.status is OrderStatus.PARTIALLY_FILLED and not (
            0.0 < snapshot.filled_quantity < order.quantity
        ):
            raise ValueError("PARTIALLY_FILLED broker response has invalid fill quantity")

        if snapshot.status is OrderStatus.CANCELLED and snapshot.filled_quantity >= order.quantity:
            raise ValueError("CANCELLED broker response cannot represent a fully filled order")

    def _transition(
        self,
        client_order_id: str,
        target: OrderStatus,
        reason: str,
    ) -> None:
        """Apply and journal one strictly validated lifecycle transition."""
        current = self._states.get(client_order_id)
        if current is not None:
            OrderStateMachine.transition(current, target)
        self._states[client_order_id] = target
        self._events.append(
            ExecutionEvent(
                client_order_id=client_order_id,
                from_status=current,
                to_status=target,
                timestamp=pd.Timestamp.now(tz="Asia/Kolkata"),
                reason=reason,
            )
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
            self._transition(client_order_id, OrderStatus.UNKNOWN, "broker returned no order state")
            self._orders[client_order_id] = unknown
            return unknown

        prior = self._orders.get(client_order_id)
        if prior is None:
            raise KeyError(f"order not found: {client_order_id}")
        order = self._order_requests.get(client_order_id)
        if order is None:
            raise KeyError(f"order request not found: {client_order_id}")
        self._validate_broker_snapshot(order, snapshot)

        current = self._states.get(client_order_id)
        if current is None:
            self._states[client_order_id] = snapshot.status
        elif current is not snapshot.status:
            self._transition(client_order_id, snapshot.status, "broker refresh")
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

        self._transition(client_order_id, OrderStatus.CANCEL_PENDING, "cancellation requested")
        snapshot = self.adapter.cancel(client_order_id)
        if snapshot.status is not OrderStatus.CANCEL_PENDING:
            self._transition(client_order_id, snapshot.status, snapshot.reason or "cancellation result")
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

    @property
    def events(self) -> tuple[ExecutionEvent, ...]:
        """Return immutable lifecycle events."""
        return tuple(self._events)

    def metrics(self) -> ExecutionMetrics:
        """Calculate execution-quality metrics from the in-memory journal."""
        snapshots = tuple(self._orders.values())
        orders = len(snapshots)
        accepted = sum(
            s.status not in {
                OrderStatus.REJECTED_LOCAL,
                OrderStatus.REJECTED_BROKER,
                OrderStatus.FAILED,
            }
            for s in snapshots
        )
        filled = sum(s.status is OrderStatus.FILLED for s in snapshots)
        partial = sum(s.status is OrderStatus.PARTIALLY_FILLED for s in snapshots)
        rejected = sum(
            s.status in {OrderStatus.REJECTED_LOCAL, OrderStatus.REJECTED_BROKER, OrderStatus.FAILED}
            for s in snapshots
        )
        unknown = sum(s.status is OrderStatus.UNKNOWN for s in snapshots)
        requested = sum(s.requested_quantity for s in snapshots)
        filled_qty = sum(s.filled_quantity for s in snapshots)
        fees = sum(fill.fee for fills in self._fills.values() for fill in fills)
        # Latency is not persisted in OrderSnapshot, so this metric is zero
        # until callers persist ExecutionResult latency externally.
        average_latency = 0.0
        return ExecutionMetrics(
            orders=orders,
            accepted_orders=accepted,
            filled_orders=filled,
            partially_filled_orders=partial,
            rejected_orders=rejected,
            unknown_orders=unknown,
            requested_quantity=requested,
            filled_quantity=filled_qty,
            total_fees=fees,
            average_latency_ms=average_latency,
            fill_ratio=(filled_qty / requested) if requested else 0.0,
            rejection_rate=(rejected / orders) if orders else 0.0,
        )

    def reconcile_positions(self, local: tuple[PositionSnapshot, ...]) -> bool:
        """Compare local positions with the authoritative broker snapshot.

        Reconciliation is fail-closed: duplicate symbols, non-finite values,
        or any quantity/price mismatch make the reconciliation invalid.
        """
        broker = self.adapter.positions()

        def canonical(
            positions: tuple[PositionSnapshot, ...],
        ) -> dict[str, tuple[float, float]]:
            result: dict[str, tuple[float, float]] = {}
            for item in positions:
                if item.symbol in result:
                    return {}
                if not pd.Series([item.quantity, item.average_price]).map(pd.isna).any():
                    result[item.symbol] = (item.quantity, item.average_price)
                else:
                    return {}
            return result

        local_map = canonical(local)
        broker_map = canonical(broker)
        if not local_map and local:
            return False
        if not broker_map and broker:
            return False
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
    "ExecutionEvent",
    "ExecutionMetrics",
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
