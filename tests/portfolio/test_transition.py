"""Position-transition contract tests."""

from __future__ import annotations

from portfolio.contracts import PortfolioPosition, TradeIntent
from portfolio.transition import (
    PositionTransition,
    classify_position_transition,
)


def test_open_transition() -> None:
    result = classify_position_transition(
        None,
        TradeIntent("INFY", 10, 1500, "BUY"),
    )
    assert result.transition is PositionTransition.OPEN
    assert result.projected_quantity == 10


def test_increase_long_transition() -> None:
    result = classify_position_transition(
        PortfolioPosition("INFY", 10, 1500),
        TradeIntent("INFY", 5, 1500, "BUY"),
    )
    assert result.transition is PositionTransition.INCREASE
    assert result.projected_quantity == 15


def test_reduce_long_transition() -> None:
    result = classify_position_transition(
        PortfolioPosition("INFY", 10, 1500),
        TradeIntent("INFY", 5, 1500, "SELL"),
    )
    assert result.transition is PositionTransition.REDUCE
    assert result.projected_quantity == 5


def test_flatten_long_transition() -> None:
    result = classify_position_transition(
        PortfolioPosition("INFY", 10, 1500),
        TradeIntent("INFY", 10, 1500, "SELL"),
    )
    assert result.transition is PositionTransition.FLATTEN
    assert result.projected_quantity == 0


def test_reverse_long_to_short_transition() -> None:
    result = classify_position_transition(
        PortfolioPosition("INFY", 10, 1500),
        TradeIntent("INFY", 15, 1500, "SELL"),
    )
    assert result.transition is PositionTransition.REVERSE
    assert result.projected_quantity == -5


def test_short_transitions_are_signed_correctly() -> None:
    increase = classify_position_transition(
        PortfolioPosition("INFY", -10, 1500),
        TradeIntent("INFY", 5, 1500, "SELL"),
    )
    reduce = classify_position_transition(
        PortfolioPosition("INFY", -10, 1500),
        TradeIntent("INFY", 5, 1500, "BUY"),
    )
    flatten = classify_position_transition(
        PortfolioPosition("INFY", -10, 1500),
        TradeIntent("INFY", 10, 1500, "BUY"),
    )

    assert increase.transition is PositionTransition.INCREASE
    assert reduce.transition is PositionTransition.REDUCE
    assert flatten.transition is PositionTransition.FLATTEN
