"""Deterministic in-process automation event bus."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from .contracts import StageEvent


Handler = Callable[[StageEvent], None]


class EventBus:
    """Publish events synchronously in registration order."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        """Subscribe a handler to one event type."""
        self._handlers[event_type].append(handler)

    def publish(self, event: StageEvent) -> None:
        """Publish to exact-event and wildcard subscribers."""
        for handler in (
            *self._handlers.get(event.event_type, []),
            *self._handlers.get("*", []),
        ):
            handler(event)
