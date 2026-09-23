"""Optional volatility-aware risk sizing.

No numeric volatility reduction is frozen by the current trading
specification, so the default policy is neutral.
"""

from __future__ import annotations

import math


def volatility_size_factor(
    *,
    entry_price: float,
    atr: float | None,
    high_volatility: bool,
    high_volatility_factor: float = 1.0,
    max_atr_fraction: float | None = None,
) -> float:
    """Return a deterministic volatility sizing factor."""
    if entry_price <= 0 or not math.isfinite(entry_price):
        raise ValueError("entry_price must be positive and finite")
    if (
        not math.isfinite(high_volatility_factor)
        or not 0 < high_volatility_factor <= 1
    ):
        raise ValueError("high_volatility_factor must be in (0, 1]")

    if atr is not None:
        if not math.isfinite(float(atr)) or float(atr) < 0:
            raise ValueError("atr must be finite and non-negative")

        if (
            max_atr_fraction is not None
            and atr / entry_price > max_atr_fraction
        ):
            return 0.0

    if high_volatility:
        return high_volatility_factor

    return 1.0
