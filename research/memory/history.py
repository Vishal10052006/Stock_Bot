"""RB-9 historical research memory without editing STOCK_BOT long-term memory."""
from __future__ import annotations
from collections import defaultdict
from research.contracts import ResearchEvent


class EventHistory:
    def __init__(self) -> None:
        self._events: dict[str, list[ResearchEvent]] = defaultdict(list)

    def add(self, event: ResearchEvent) -> None:
        key = event.symbol or "__MARKET__"
        self._events[key].append(event)

    def similar(self, symbol: str, event_type: str) -> tuple[ResearchEvent, ...]:
        return tuple(e for e in self._events.get(symbol, ()) if e.event_type.value == event_type)
