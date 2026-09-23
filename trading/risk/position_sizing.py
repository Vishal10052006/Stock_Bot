"""Risk-first position sizing utilities.

Reference: TRADING_SPECIFICATION.md sections 8 and 18.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionSizingResult:
    """Deterministic result of risk-first quantity calculation."""

    risk_budget: float
    stop_distance: float
    raw_quantity: float
    quantity: float


def floor_to_step(quantity: float, step: float) -> float:
    """Round a non-negative quantity down to the configured step."""
    if not math.isfinite(quantity) or quantity < 0:
        raise ValueError("quantity must be finite and non-negative")
    if not math.isfinite(step) or step <= 0:
        raise ValueError("quantity step must be finite and positive")
    return math.floor((quantity + 1e-12) / step) * step


def calculate_position_size(
    *,
    available_equity: float,
    risk_per_trade: float,
    stop_distance: float,
    quantity_step: float = 1.0,
) -> PositionSizingResult:
    """Calculate quantity from the risk budget before portfolio caps."""
    if not math.isfinite(available_equity) or available_equity <= 0:
        raise ValueError("available_equity must be positive and finite")
    if not math.isfinite(risk_per_trade) or not 0 < risk_per_trade <= 1:
        raise ValueError("risk_per_trade must be in (0, 1]")
    if not math.isfinite(stop_distance) or stop_distance <= 0:
        raise ValueError("stop_distance must be positive and finite")

    risk_budget = available_equity * risk_per_trade
    raw_quantity = risk_budget / stop_distance
    quantity = floor_to_step(raw_quantity, quantity_step)

    return PositionSizingResult(
        risk_budget=risk_budget,
        stop_distance=stop_distance,
        raw_quantity=raw_quantity,
        quantity=quantity,
    )
