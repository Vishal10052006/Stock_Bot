"""Volatility interpretation using existing causal volatility features."""
from __future__ import annotations
from typing import Any, Mapping


def analyze_volatility(features: Mapping[str, Any]) -> dict[str, Any]:
    """Interpret normalized ATR, bands and realized volatility."""
    def number(name: str) -> float | None:
        try:
            value = features.get(name)
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    atr = number("atr_normalized")
    bb = number("bb_width_normalized")
    rv = number("realized_volatility_20")
    available = [value for value in (atr, bb, rv) if value is not None]
    return {
        "atr_normalized": atr,
        "bb_width_normalized": bb,
        "realized_volatility_20": rv,
        "state": "AVAILABLE" if available else "UNAVAILABLE",
        "observations": len(available),
    }
