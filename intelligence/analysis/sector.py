"""PIT sector-context adapter."""
from __future__ import annotations
from typing import Any, Mapping


def analyze_sector_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize existing PIT-aligned sector context."""
    return {
        "sector_return_1": context.get("sector_return_1"),
        "sector_return_3": context.get("sector_return_3"),
        "sector_return_12": context.get("sector_return_12"),
        "sector_volatility_20": context.get("sector_volatility_20"),
        "available": any(
            context.get(name) is not None
            for name in (
                "sector_return_1", "sector_return_3",
                "sector_return_12", "sector_volatility_20",
            )
        ),
    }
