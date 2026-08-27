"""
Stock Bot — Feature Engine

Calculates normalized technical features from market price data.
"""

from collections.abc import Sequence
from math import isfinite

from features.models import FeatureSet


def calculate_features(
    symbol: str,
    prices: Sequence[float],
    timestamp: object,
) -> FeatureSet:
    """
    Calculate a minimal deterministic feature set.

    The first Phase-1 implementation intentionally keeps the
    feature calculation simple and dependency-free.

    Features:
        - latest_price: Most recent market price.
        - price_change_pct: Percentage change from first to latest price.
        - price_range_pct: Percentage range between minimum and maximum price.

    Raises:
        ValueError: If the symbol or price data is invalid.
    """

    if not symbol:
        raise ValueError("symbol must not be empty")

    if not prices:
        raise ValueError("prices must not be empty")

    # Normalize provider/input values before performing calculations.
    try:
        normalized_prices = tuple(float(price) for price in prices)
    except (TypeError, ValueError) as exc:
        raise ValueError("prices must be numeric") from exc

    # Reject NaN and infinite values before they enter feature calculations.
    if any(not isfinite(price) for price in normalized_prices):
        raise ValueError("prices must be finite")

    # Feature calculations require strictly positive market prices.
    if any(price <= 0 for price in normalized_prices):
        raise ValueError("prices must be greater than zero")

    latest_price = normalized_prices[-1]
    first_price = normalized_prices[0]
    minimum_price = min(normalized_prices)
    maximum_price = max(normalized_prices)

    price_change_pct = ((latest_price - first_price) / first_price) * 100.0
    price_range_pct = ((maximum_price - minimum_price) / minimum_price) * 100.0

    return FeatureSet(
        symbol=symbol,
        timestamp=timestamp,
        values={
            "latest_price": latest_price,
            "price_change_pct": price_change_pct,
            "price_range_pct": price_range_pct,
        },
    )
