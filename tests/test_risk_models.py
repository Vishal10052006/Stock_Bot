"""
Tests for Stock Bot risk data contracts.
"""

import pytest

from risk.models import RiskResult


def test_valid_approved_risk_result():
    """An approved risk result should be accepted."""

    result = RiskResult(
        decision="APPROVE",
        risk_score=0.25,
        reason="Risk is within the allowed threshold.",
    )

    assert result.decision == "APPROVE"
    assert result.risk_score == 0.25


def test_valid_rejected_risk_result():
    """A rejected risk result should be accepted."""

    result = RiskResult(
        decision="REJECT",
        risk_score=0.90,
        reason="Risk exceeds the allowed threshold.",
    )

    assert result.decision == "REJECT"


def test_invalid_decision_is_rejected():
    """Unsupported risk decisions should be rejected."""

    with pytest.raises(ValueError):
        RiskResult(
            decision="BUY",
            risk_score=0.25,
            reason="Invalid decision.",
        )


def test_invalid_risk_score_is_rejected():
    """Risk scores outside 0..1 should be rejected."""

    with pytest.raises(ValueError):
        RiskResult(
            decision="APPROVE",
            risk_score=1.5,
            reason="Invalid risk score.",
        )
