"""
Stock Bot — Signal Engine

Converts normalized feature values into a normalized trading signal.

Phase 1 intentionally uses a deterministic rule-based signal generator.
This provides a stable contract for the strategy and risk layers before
more sophisticated models are introduced.
"""

from math import isfinite

from features.models import FeatureSet
from signals.models import TradingSignal


# Phase-1 signal thresholds.
BUY_THRESHOLD_PCT = 2.0
SELL_THRESHOLD_PCT = -2.0


def generate_signal(features: FeatureSet) -> TradingSignal:
    """
    Generate a trading signal from normalized market features.

    Rules:
        - price_change_pct >= 2.0  -> BUY
        - price_change_pct <= -2.0 -> SELL
        - otherwise                -> HOLD

    Confidence is based on the magnitude of the price change and is
    capped at 1.0.
    """

    price_change_pct = features.values.get("price_change_pct")

    if price_change_pct is None:
        raise ValueError("price_change_pct feature is required")

    # Reject NaN and infinite feature values before signal generation.
    if not isfinite(float(price_change_pct)):
        raise ValueError("price_change_pct must be finite")

    # Scale absolute price movement into a 0..1 confidence value.
    confidence = min(abs(price_change_pct) / 5.0, 1.0)

    if price_change_pct >= BUY_THRESHOLD_PCT:
        signal = "BUY"
    elif price_change_pct <= SELL_THRESHOLD_PCT:
        signal = "SELL"
    else:
        signal = "HOLD"

    return TradingSignal(
        symbol=features.symbol,
        signal=signal,
        confidence=confidence,
        timestamp=features.timestamp,
        source="rule_based",
    )
