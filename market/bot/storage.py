"""Storage boundary and causal freshness checks for MarketContext."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from .contracts import MarketContext
from .failure import StaleMarketDataError


@runtime_checkable
class MarketContextStore(Protocol):
    def put(self, context: MarketContext) -> None: ...
    def get(self, benchmark: str, timestamp: datetime) -> MarketContext | None: ...
    def get_latest_at_or_before(
        self,
        benchmark: str,
        decision_timestamp: datetime,
        *,
        max_age: timedelta,
    ) -> MarketContext | None: ...


def require_fresh_market_context(
    context: MarketContext,
    *,
    decision_timestamp: datetime,
    max_age: timedelta,
) -> MarketContext:
    """Fail closed when a MarketContext is future-dated or too old."""
    if decision_timestamp.tzinfo is None:
        raise ValueError("decision_timestamp must be timezone-aware")
    if max_age < timedelta(0):
        raise ValueError("max_age must not be negative")
    age = decision_timestamp - context.timestamp
    if age < timedelta(0):
        raise StaleMarketDataError(
            "market context cannot be from the future of decision timestamp"
        )
    if age > max_age:
        raise StaleMarketDataError(
            f"market context is stale by {age}; max_age={max_age}"
        )
    return context


class InMemoryMarketContextStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], MarketContext] = {}

    @staticmethod
    def _key(benchmark: str, timestamp: datetime) -> tuple[str, str]:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return benchmark.strip().upper(), timestamp.isoformat()

    def put(self, context: MarketContext) -> None:
        self._items[self._key(context.benchmark, context.timestamp)] = context

    def get(self, benchmark: str, timestamp: datetime) -> MarketContext | None:
        return self._items.get(self._key(benchmark, timestamp))

    def get_latest_at_or_before(
        self,
        benchmark: str,
        decision_timestamp: datetime,
        *,
        max_age: timedelta,
    ) -> MarketContext | None:
        """Return the newest causal context that is still fresh."""
        if decision_timestamp.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware")
        if max_age < timedelta(0):
            raise ValueError("max_age must not be negative")
        benchmark_key = benchmark.strip().upper()
        candidates = [
            context
            for (stored_benchmark, _), context in self._items.items()
            if stored_benchmark == benchmark_key
            and context.timestamp <= decision_timestamp
        ]
        if not candidates:
            return None
        context = max(candidates, key=lambda item: item.timestamp)
        return require_fresh_market_context(
            context,
            decision_timestamp=decision_timestamp,
            max_age=max_age,
        )
