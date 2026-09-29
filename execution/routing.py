"""Deterministic broker-neutral order-routing policy.

Routing is deliberately separated from order submission.  It chooses a
healthy broker route from explicit, point-in-time execution quotes; it never
changes Risk-approved quantity, creates orders, or bypasses Safety.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from execution.engine import BrokerAdapter, OrderRequest


@dataclass(frozen=True, slots=True)
class RouteQuote:
    """Execution quote supplied by a broker adapter or routing service."""

    broker: str
    available_quantity: float
    expected_slippage_bps: float
    fee_bps: float
    latency_ms: float = 0.0
    healthy: bool = True

    def __post_init__(self) -> None:
        if not self.broker.strip():
            raise ValueError("broker must not be empty")
        values = (
            self.available_quantity,
            self.expected_slippage_bps,
            self.fee_bps,
            self.latency_ms,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("route quote values must be finite")
        if self.available_quantity < 0:
            raise ValueError("available_quantity must be non-negative")
        if self.expected_slippage_bps < 0 or self.fee_bps < 0:
            raise ValueError("execution costs must be non-negative")
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")


@dataclass(frozen=True, slots=True)
class RoutingPolicy:
    """Fail-closed deterministic route-selection policy."""

    max_slippage_bps: float = 100.0
    max_latency_ms: float = 5_000.0
    require_full_quantity: bool = True
    slippage_weight: float = 1.0
    fee_weight: float = 1.0
    latency_weight: float = 0.0

    def __post_init__(self) -> None:
        values = (
            self.max_slippage_bps,
            self.max_latency_ms,
            self.slippage_weight,
            self.fee_weight,
            self.latency_weight,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("routing policy values must be finite")
        if self.max_slippage_bps < 0 or self.max_latency_ms < 0:
            raise ValueError("routing limits must be non-negative")
        if (
            self.slippage_weight < 0
            or self.fee_weight < 0
            or self.latency_weight < 0
        ):
            raise ValueError("routing weights must be non-negative")
        if (
            self.slippage_weight
            + self.fee_weight
            + self.latency_weight
            <= 0
        ):
            raise ValueError("at least one routing weight must be positive")


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Immutable routing result; no broker order has been submitted."""

    broker: str
    score: float
    reason: str
    considered: tuple[str, ...]


class SmartOrderRouter:
    """Select one broker route without modifying the order."""

    VERSION = "ROUTER-v1.0"

    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        self.policy = policy or RoutingPolicy()

    def select(
        self,
        order: OrderRequest,
        quotes: Sequence[RouteQuote],
    ) -> RouteDecision:
        if not isinstance(order, OrderRequest):
            raise TypeError("order must be an OrderRequest")
        if not quotes:
            raise ValueError("no broker route quotes were supplied")

        candidates: list[RouteQuote] = []
        seen: set[str] = set()
        for quote in quotes:
            broker = quote.broker.strip()
            if broker in seen:
                raise ValueError(f"duplicate broker route: {broker}")
            seen.add(broker)

            if not quote.healthy:
                continue
            if quote.expected_slippage_bps > self.policy.max_slippage_bps:
                continue
            if quote.latency_ms > self.policy.max_latency_ms:
                continue
            if self.policy.require_full_quantity and (
                quote.available_quantity + 1e-12 < order.quantity
            ):
                continue
            if not self.policy.require_full_quantity and quote.available_quantity <= 0:
                continue
            candidates.append(quote)

        if not candidates:
            raise ValueError("no broker route satisfies routing policy")

        def score(quote: RouteQuote) -> tuple[float, float, str]:
            total = (
                self.policy.slippage_weight * quote.expected_slippage_bps
                + self.policy.fee_weight * quote.fee_bps
                + self.policy.latency_weight * quote.latency_ms
            )
            return total, quote.latency_ms, quote.broker

        selected = min(candidates, key=score)
        considered = tuple(sorted(quote.broker for quote in candidates))
        return RouteDecision(
            broker=selected.broker,
            score=score(selected)[0],
            reason="lowest deterministic execution-cost score among eligible routes",
            considered=considered,
        )

    def select_adapter(
        self,
        order: OrderRequest,
        adapters: Mapping[str, BrokerAdapter],
        quotes: Sequence[RouteQuote],
    ) -> tuple[BrokerAdapter, RouteDecision]:
        decision = self.select(order, quotes)
        try:
            adapter = adapters[decision.broker]
        except KeyError as exc:
            raise ValueError(
                f"selected broker adapter is not configured: {decision.broker}"
            ) from exc
        return adapter, decision


__all__ = [
    "RouteDecision",
    "RouteQuote",
    "RoutingPolicy",
    "SmartOrderRouter",
]
