"""Broker-neutral adapter contracts.

The Execution Engine depends only on this interface. Provider-specific APIs
must remain behind an adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from execution.engine import Fill, OrderRequest, OrderSnapshot, PositionSnapshot


class BrokerAdapter(ABC):
    """Abstract broker interface consumed by ExecutionEngine."""

    @abstractmethod
    def submit(self, order: OrderRequest) -> OrderSnapshot:
        """Submit an order exactly once for its client order identifier."""
        raise NotImplementedError

    @abstractmethod
    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        """Return the latest authoritative broker state."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self, client_order_id: str) -> OrderSnapshot:
        """Request cancellation and return authoritative state."""
        raise NotImplementedError

    @abstractmethod
    def positions(self) -> tuple[PositionSnapshot, ...]:
        """Return the authoritative broker position snapshot."""
        raise NotImplementedError


__all__ = ["BrokerAdapter", "Fill"]