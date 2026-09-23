"""Stop-loss validation for the Risk Engine.

Stop construction remains upstream in trading.signals.candidate. Risk
validates the candidate rather than duplicating causal stop construction.
"""

from __future__ import annotations

import math

from trading.strategy.models import StrategyDirection


def validate_stop(
    *,
    direction: StrategyDirection,
    entry_price: float,
    stop_price: float,
) -> float:
    """Validate direction-aware stop geometry and return stop distance."""
    if not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("entry price must be positive and finite")
    if not math.isfinite(stop_price) or stop_price <= 0:
        raise ValueError("stop price must be positive and finite")

    if direction is StrategyDirection.LONG:
        if stop_price >= entry_price:
            raise ValueError("LONG stop must be below entry")
    elif direction is StrategyDirection.SHORT:
        if stop_price <= entry_price:
            raise ValueError("SHORT stop must be above entry")
    else:
        raise ValueError("Risk Engine requires LONG or SHORT")

    distance = abs(entry_price - stop_price)
    if distance <= 0 or not math.isfinite(distance):
        raise ValueError("stop distance must be positive and finite")
    return distance
