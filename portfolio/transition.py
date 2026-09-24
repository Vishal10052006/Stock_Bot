"""Deterministic position-transition classification for Portfolio -> Risk.

The classifier describes how a proposed trade changes an existing signed
position. It does not authorize, size, or execute the trade.
"""

from __future__ import annotations

from dataclasses import dataclass

from portfolio.contracts import PortfolioPosition, PositionTransition, TradeIntent


@dataclass(frozen=True, slots=True)
class PositionTransitionResult:
    """Auditable classification of one proposed position change."""

    transition: PositionTransition
    existing_quantity: float
    projected_quantity: float


def classify_position_transition(
    existing: PortfolioPosition | None,
    intent: TradeIntent,
) -> PositionTransitionResult:
    """Classify a proposed trade against the current signed position.

    Positive quantity is long and negative quantity is short. A missing
    position is treated as zero. The function is pure and deterministic.
    """
    current = existing.quantity if existing is not None else 0.0
    delta = intent.quantity if intent.side == "BUY" else -intent.quantity
    projected = current + delta

    if current == 0.0:
        transition = PositionTransition.OPEN
    elif projected == 0.0:
        transition = PositionTransition.FLATTEN
    elif current > 0 and projected > current:
        transition = PositionTransition.INCREASE
    elif current < 0 and projected < current:
        transition = PositionTransition.INCREASE
    elif (current > 0 and 0 < projected < current) or (
        current < 0 and current < projected < 0
    ):
        transition = PositionTransition.REDUCE
    elif (current > 0 > projected) or (current < 0 < projected):
        transition = PositionTransition.REVERSE
    else:
        raise ValueError("unsupported position transition")

    return PositionTransitionResult(
        transition=transition,
        existing_quantity=current,
        projected_quantity=projected,
    )
