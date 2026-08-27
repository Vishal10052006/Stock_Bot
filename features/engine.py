"""
Stock Bot — Feature Engine

Calculates normalized technical features from market price data.
"""

from collections.abc import Sequence

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
    """

    if not symbol:
        raise ValueError("symbol must not be empty")

    if not prices:
        raise ValueError("prices must not be empty")

    if any(price <= 0 for price in prices):
        raise ValueError("prices must be greater than zero")

    latest_price = float(prices[-1])
    first_price = float(prices[0])
    minimum_price = float(min(prices))
    maximum_price = float(max(prices))

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
