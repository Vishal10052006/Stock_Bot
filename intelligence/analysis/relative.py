"""Relative stock-versus-market/sector analysis."""
from __future__ import annotations
from typing import Any, Mapping


def analyze_relative_performance(features: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret already-computed relative return features."""
    market = features.get("stock_vs_market_return_1")
    sector = features.get("stock_vs_sector_return_1")
    def as_float(v: Any) -> float | None:
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None
    market_f = as_float(market)
    sector_f = as_float(sector)
    return {
        "stock_vs_market_return_1": market_f,
        "stock_vs_sector_return_1": sector_f,
        "relative_strength": market_f is not None and sector_f is not None and market_f > 0 and sector_f > 0,
        "relative_weakness": market_f is not None and sector_f is not None and market_f < 0 and sector_f < 0,
    }
