"""
Tests for the Phase-1 Stock Bot orchestrator.

Verifies the complete flow:
features -> signal -> strategy -> risk gate.
"""

from datetime import datetime

from core.stock_bot import analyze_market


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


def test_buy_pipeline_is_approved():
    """A 2% upward move should produce an approved BUY."""

    strategy, risk, approved = analyze_market(
        symbol="RELIANCE",
        prices=[2500.0, 2550.0],
        timestamp=TIMESTAMP,
    )

    assert strategy.symbol == "RELIANCE"
    assert strategy.action == "BUY"
    assert strategy.confidence == 0.4

    assert risk.decision == "APPROVE"
    assert risk.risk_score == 0.25
    assert approved is True


def test_small_price_move_produces_hold():
    """A 0.2% price movement should produce a HOLD."""

    strategy, risk, approved = analyze_market(
        symbol="RELIANCE",
        prices=[2500.0, 2505.0],
        timestamp=TIMESTAMP,
    )

    assert strategy.action == "HOLD"
    assert strategy.confidence == 0.04

    assert risk.decision == "APPROVE"
    assert approved is True


def test_downward_move_produces_sell():
    """A -3% price movement should produce a SELL."""

    strategy, risk, approved = analyze_market(
        symbol="RELIANCE",
        prices=[2500.0, 2425.0],
        timestamp=TIMESTAMP,
    )

    assert strategy.action == "SELL"
    assert strategy.confidence == 0.6
    assert approved is True
