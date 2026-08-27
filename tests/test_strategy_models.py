"""
Tests for Stock Bot strategy data contracts.
"""

import pytest

from strategies.models import StrategyDecision


def test_valid_strategy_decision():
    """A valid strategy decision should be accepted."""

    decision = StrategyDecision(
        symbol="RELIANCE",
        action="BUY",
        confidence=0.80,
        rationale="Bullish technical setup.",
    )

    assert decision.symbol == "RELIANCE"
    assert decision.action == "BUY"
    assert decision.confidence == 0.80


def test_valid_hold_decision():
    """A HOLD strategy decision should be accepted."""

    decision = StrategyDecision(
        symbol="RELIANCE",
        action="HOLD",
        confidence=0.50,
        rationale="No clear directional edge.",
    )

    assert decision.action == "HOLD"


def test_invalid_action_is_rejected():
    """Unsupported strategy actions should be rejected."""

    with pytest.raises(ValueError):
        StrategyDecision(
            symbol="RELIANCE",
            action="INVALID",
            confidence=0.80,
            rationale="Invalid action.",
        )


def test_invalid_confidence_is_rejected():
    """Confidence outside 0..1 should be rejected."""

    with pytest.raises(ValueError):
        StrategyDecision(
            symbol="RELIANCE",
            action="BUY",
            confidence=1.5,
            rationale="Invalid confidence.",
        )
