"""
Tests for the Stock Bot risk execution gate.
"""

from strategies.models import StrategyDecision
from risk.models import RiskResult
from risk.gate import approve_trade


def test_approved_risk_allows_trade():
    """An approved risk decision should allow execution."""

    strategy = StrategyDecision(
        symbol="RELIANCE",
        action="BUY",
        confidence=0.85,
        rationale="Positive technical setup.",
    )

    risk = RiskResult(
        decision="APPROVE",
        risk_score=0.25,
        reason="Risk is within the allowed threshold.",
    )

    assert approve_trade(strategy, risk) is True


def test_rejected_risk_blocks_trade():
    """A rejected risk decision should block execution."""

    strategy = StrategyDecision(
        symbol="RELIANCE",
        action="BUY",
        confidence=0.85,
        rationale="Positive technical setup.",
    )

    risk = RiskResult(
        decision="REJECT",
        risk_score=0.90,
        reason="Risk exceeds the allowed threshold.",
    )

    assert approve_trade(strategy, risk) is False
