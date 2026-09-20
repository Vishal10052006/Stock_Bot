"""Storage adapter boundary for AnalysisContext.

The adapter intentionally stores AnalysisContext records through an injected
backend. It does not introduce a second database architecture.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from intelligence.analysis.contracts import AnalysisContext


class AnalysisContextStore(Protocol):
    """Protocol implemented by an existing/persistent storage backend."""

    def put(self, context: AnalysisContext) -> None:
        ...

    def get(self, symbol: str, timestamp: object) -> AnalysisContext | None:
        ...


class InMemoryAnalysisContextStore:
    """Reference store used by tests and local development."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], AnalysisContext] = {}

    def put(self, context: AnalysisContext) -> None:
        key = (context.symbol, context.timestamp.isoformat())
        self._items[key] = context

    def get(self, symbol: str, timestamp: object) -> AnalysisContext | None:
        key = (symbol.upper(), _timestamp_key(timestamp))
        return self._items.get(key)


def _timestamp_key(timestamp: object) -> str:
    """Normalize lookup timestamps to the AnalysisContext key format."""
    return datetime.fromisoformat(
        str(timestamp).replace("Z", "+00:00")
    ).isoformat()
