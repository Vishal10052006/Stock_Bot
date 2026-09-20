"""Technical interpretation of existing Phase 4/5 outputs.

This module interprets existing causal indicators/features. It deliberately
performs no new indicator calculations and emits no trade orders.
"""
from __future__ import annotations

from typing import Any, Mapping


def _number(features: Mapping[str, Any], name: str) -> float | None:
    value = features.get(name)
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_technical(features: Mapping[str, Any]) -> dict[str, Any]:
    """Derive deterministic technical context from existing features."""
    ema_9_20 = _number(features, "ema_9_20_distance_pct")
    ema_20_50 = _number(features, "ema_20_50_distance_pct")
    price_vwap = _number(features, "vwap_distance_pct")
    rsi = _number(features, "rsi_14")
    macd_hist = _number(features, "macd_histogram")
    roc = _number(features, "roc_14")

    bullish_votes = 0
    bearish_votes = 0
    observations = 0

    for value, positive, negative in [
        (ema_9_20, lambda x: x > 0, lambda x: x < 0),
        (ema_20_50, lambda x: x > 0, lambda x: x < 0),
        (price_vwap, lambda x: x > 0, lambda x: x < 0),
        (macd_hist, lambda x: x > 0, lambda x: x < 0),
        (roc, lambda x: x > 0, lambda x: x < 0),
    ]:
        if value is None:
            continue
        observations += 1
        if positive(value):
            bullish_votes += 1
        elif negative(value):
            bearish_votes += 1

    if rsi is not None:
        observations += 1
        if rsi > 50:
            bullish_votes += 1
        elif rsi < 50:
            bearish_votes += 1

    if observations == 0:
        direction = "UNKNOWN"
        state = "UNAVAILABLE"
    elif bullish_votes > bearish_votes:
        direction = "BULLISH"
        state = "ALIGNED" if bullish_votes >= observations * 0.67 else "NEUTRAL"
    elif bearish_votes > bullish_votes:
        direction = "BEARISH"
        state = "ALIGNED" if bearish_votes >= observations * 0.67 else "NEUTRAL"
    else:
        direction = "NEUTRAL"
        state = "CONFLICT"

    momentum = "UNKNOWN" if rsi is None and macd_hist is None else (
        "POSITIVE" if (rsi is not None and rsi > 50) or (macd_hist is not None and macd_hist > 0)
        else "NEGATIVE"
    )

    return {
        "direction": direction,
        "state": state,
        "trend_alignment": direction,
        "momentum": momentum,
        "observations": observations,
        "bullish_votes": bullish_votes,
        "bearish_votes": bearish_votes,
    }
