"""Storage boundary for MarketContext; no second database is introduced."""
from __future__ import annotations
from datetime import datetime
from typing import Protocol
from .contracts import MarketContext

class MarketContextStore(Protocol):
    def put(self, context: MarketContext) -> None: ...
    def get(self, benchmark: str, timestamp: datetime) -> MarketContext | None: ...

class InMemoryMarketContextStore:
    def __init__(self) -> None:
        self._items: dict[tuple[str,str],MarketContext] = {}
    @staticmethod
    def _key(benchmark: str, timestamp: datetime) -> tuple[str, str]:
        if timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return benchmark.strip().upper(), timestamp.isoformat()

    def put(self, context: MarketContext) -> None:
        self._items[self._key(context.benchmark, context.timestamp)] = context

    def get(self, benchmark: str, timestamp: datetime) -> MarketContext | None:
        return self._items.get(self._key(benchmark, timestamp))
