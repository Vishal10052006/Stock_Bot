"""Market/index context adapter."""
from __future__ import annotations
from typing import Any, Mapping


def analyze_market_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize existing market-context fields into an analysis block."""
    return {
        "market_return_1": context.get("market_return_1"),
        "market_return_3": context.get("market_return_3"),
        "market_return_12": context.get("market_return_12"),
        "market_volatility_20": context.get("market_volatility_20"),
        "available": any(
            context.get(name) is not None
            for name in (
                "market_return_1", "market_return_3",
                "market_return_12", "market_volatility_20",
            )
        ),
    }
