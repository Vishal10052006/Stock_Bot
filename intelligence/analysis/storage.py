"""Storage adapter boundary for AnalysisContext.

The adapter intentionally stores JSON-safe dictionaries and does not create a
second database. A concrete backend can be wired into the existing STOCK_BOT
storage layer later.
"""
from __future__ import annotations
from dataclasses import asdict
from typing import Protocol

from intelligence.analysis.contracts import AnalysisContext


class AnalysisContextStore(Protocol):
    """Protocol implemented by an existing/persistent storage backend."""
    def put(self, context: AnalysisContext) -> None: ...
    def get(self, symbol: str, timestamp: object) -> AnalysisContext | None: ...


class InMemoryAnalysisContextStore:
    """Deterministic test/reference store; production DB is injected separately."""
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AnalysisContext] = {}

    def put(self, context: AnalysisContext) -> None:
        key = (context.symbol, context.timestamp.isoformat())
        self._items[key] = context

    def get(self, symbol: str, timestamp: object) -> AnalysisContext | None:
        key = (symbol.upper(), str(timestamp))
        return self._items.get(key)
