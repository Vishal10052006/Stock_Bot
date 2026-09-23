"""Deterministic minimum-R target construction.

Reference: TRADING_SPECIFICATION.md section 16.
"""

from __future__ import annotations

import math

from trading.strategy.models import StrategyDirection


def build_target(
    *,
    direction: StrategyDirection,
    entry_price: float,
    stop_distance: float,
    target_multiple_r: float,
) -> float:
    """Construct a direction-aware target from initial price risk."""
    if not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("entry price must be positive and finite")
    if not math.isfinite(stop_distance) or stop_distance <= 0:
        raise ValueError("stop distance must be positive and finite")
    if not math.isfinite(target_multiple_r) or target_multiple_r <= 0:
        raise ValueError("target_multiple_r must be positive and finite")

    distance = stop_distance * target_multiple_r

    if direction is StrategyDirection.LONG:
        target = entry_price + distance
    elif direction is StrategyDirection.SHORT:
        target = entry_price - distance
    else:
        raise ValueError("Risk Engine requires LONG or SHORT")

    if not math.isfinite(target) or target <= 0:
        raise ValueError("target must be positive and finite")

    return target
