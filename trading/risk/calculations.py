"""Deterministic trade-risk calculations."""

from __future__ import annotations

from math import floor, isfinite

from trading.signals.models import CandidateDirection, TradeCandidate

from .contracts import PositionRisk, RiskPolicy


def stop_distance(candidate: TradeCandidate) -> float:
    """Return the absolute decision-time stop distance."""
    distance = abs(float(candidate.entry_price) - float(candidate.stop_price))
    if not isfinite(distance) or distance <= 0:
        raise ValueError("candidate stop distance must be finite and positive")
    return distance


def risk_budget(equity: float, policy: RiskPolicy) -> float:
    """Return maximum planned loss allowed for a new trade."""
    if not isfinite(float(equity)) or equity <= 0:
        raise ValueError("equity must be positive and finite")
    return float(equity) * policy.risk_per_trade


def reward_risk_ratio(
    *,
    direction: CandidateDirection,
    entry_price: float,
    stop_price: float,
    target_price: float | None,
) -> float | None:
    """Return R:R when a target is supplied."""
    if target_price is None:
        return None
    risk = abs(float(entry_price) - float(stop_price))
    if risk <= 0:
        raise ValueError("risk distance must be positive")
    reward = (
        float(target_price) - float(entry_price)
        if direction is CandidateDirection.LONG
        else float(entry_price) - float(target_price)
    )
    if reward < 0:
        raise ValueError("target must be on the profitable side of entry")
    return reward / risk


def maximum_quantity(
    *,
    equity: float,
    candidate: TradeCandidate,
    policy: RiskPolicy,
    target_price: float | None = None,
    risk_multiplier: float = 1.0,
    quantity_step: float = 1.0,
    quantity_cap: float | None = None,
) -> PositionRisk:
    """Calculate risk-first quantity before portfolio caps."""
    if quantity_step <= 0 or risk_multiplier <= 0:
        raise ValueError("quantity_step and risk_multiplier must be positive")

    distance = stop_distance(candidate)
    budget = risk_budget(equity, policy) * risk_multiplier
    raw_quantity = budget / distance
    quantity = floor(raw_quantity / quantity_step) * quantity_step

    if quantity_cap is not None:
        if quantity_cap <= 0:
            raise ValueError("quantity_cap must be positive")
        quantity = min(quantity, quantity_cap)

    quantity = float(quantity)
    rr = reward_risk_ratio(
        direction=candidate.direction,
        entry_price=candidate.entry_price,
        stop_price=candidate.stop_price,
        target_price=target_price,
    )

    return PositionRisk(
        entry_price=float(candidate.entry_price),
        stop_price=float(candidate.stop_price),
        stop_distance=distance,
        risk_budget=budget,
        risk_per_unit=distance,
        quantity=quantity,
        notional=quantity * float(candidate.entry_price),
        reward_risk_ratio=rr,
    )


def cap_quantity(quantity: float, *, caps: list[float], quantity_step: float = 1.0) -> float:
    """Apply deterministic non-negative quantity caps."""
    if quantity < 0 or not isfinite(float(quantity)):
        raise ValueError("quantity must be finite and non-negative")
    if quantity_step <= 0:
        raise ValueError("quantity_step must be positive")
    for cap in caps:
        if cap < 0 or not isfinite(float(cap)):
            raise ValueError("quantity caps must be finite and non-negative")
    capped = min([quantity, *caps])
    return float(floor(capped / quantity_step) * quantity_step)
