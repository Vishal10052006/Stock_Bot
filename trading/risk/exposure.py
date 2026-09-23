"""Portfolio exposure calculations for the Risk Engine.

Reference: TRADING_SPECIFICATION.md sections 12 and 18.
"""

from __future__ import annotations

import math

from .position_sizing import floor_to_step


def gross_exposure_after(
    *,
    current_gross_exposure: float,
    entry_price: float,
    quantity: float,
) -> float:
    """Return gross exposure after adding a new position."""
    values = (current_gross_exposure, entry_price, quantity)

    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("exposure inputs must be finite")
    if current_gross_exposure < 0:
        raise ValueError("current gross exposure must be non-negative")
    if entry_price <= 0:
        raise ValueError("entry price must be positive")
    if quantity < 0:
        raise ValueError("quantity must be non-negative")

    return current_gross_exposure + entry_price * quantity


def max_quantity_for_exposure(
    *,
    available_exposure: float,
    entry_price: float,
    quantity_step: float = 1.0,
) -> float:
    """Return the largest quantity permitted by an exposure budget."""
    if not math.isfinite(available_exposure) or available_exposure < 0:
        raise ValueError("available_exposure must be finite and non-negative")
    if not math.isfinite(entry_price) or entry_price <= 0:
        raise ValueError("entry_price must be positive and finite")
    if not math.isfinite(quantity_step) or quantity_step <= 0:
        raise ValueError("quantity_step must be positive and finite")

    raw = available_exposure / entry_price
    return floor_to_step(raw, quantity_step)
