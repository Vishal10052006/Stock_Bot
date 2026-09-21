"""ResearchContext adapter for the Analysis Bot boundary."""
from __future__ import annotations
from typing import Any


def research_summary(context: Any | None) -> dict[str, Any]:
    """Extract only context metadata from ResearchContext when available."""
    if context is None:
        return {"available": False}
    result: dict[str, Any] = {"available": True}
    for field in ("symbol", "as_of", "events", "sentiment", "sentiments", "impacts", "provenance"):
        if hasattr(context, field):
            value = getattr(context, field)
            if field == "as_of" and value is not None:
                value = value.isoformat()
            if field == "sentiments" and hasattr(context, "sentiment"):
                continue
            result[field] = value
    return result
