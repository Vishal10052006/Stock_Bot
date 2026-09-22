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
    def put(self, context: MarketContext) -> None:
        self._items[(context.benchmark,context.timestamp.isoformat())]=context
    def get(self, benchmark: str, timestamp: datetime) -> MarketContext | None:
        return self._items.get((benchmark.strip().upper(),timestamp.isoformat()))
