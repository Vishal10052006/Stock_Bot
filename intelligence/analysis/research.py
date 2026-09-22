"""ResearchContext adapter for the Analysis Bot boundary."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


def research_summary(context: Any | None) -> dict[str, Any]:
    """Extract stable ResearchContext metadata without recreating research logic."""
    if context is None:
        return {"available": False}

    result: dict[str, Any] = {"available": True}
    if isinstance(context, Mapping):
        for field in (
            "symbol",
            "as_of",
            "events",
            "sentiment",
            "sentiments",
            "impacts",
            "provenance",
            "research_version",
        ):
            if field not in context:
                continue
            value = context[field]
            if field == "as_of" and value is not None:
                value = pd.Timestamp(value).isoformat()
            if field == "sentiments" and "sentiment" in context:
                continue
            result[field] = value
        return result

    for field in (
        "symbol",
        "as_of",
        "events",
        "sentiment",
        "sentiments",
        "impacts",
        "provenance",
        "research_version",
    ):
        if hasattr(context, field):
            value = getattr(context, field)
            if field == "as_of" and value is not None:
                value = pd.Timestamp(value).isoformat()
            if field == "sentiments" and hasattr(context, "sentiment"):
                continue
            result[field] = value
    return result
