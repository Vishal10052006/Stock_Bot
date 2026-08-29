"""
Tests for the Stock Bot strategy engine.
"""

from datetime import datetime

from signals.models import TradingSignal
from strategies.engine import generate_strategy


def test_buy_signal_generates_buy_strategy():
    """A BUY signal should produce a BUY strategy decision."""

    signal = TradingSignal(
        symbol="RELIANCE",
        signal="BUY",
        confidence=0.85,
        timestamp=datetime(2026, 8, 27, 9, 30),
        source="technical",
    )

    decision = generate_strategy(signal)

    assert decision.symbol == "RELIANCE"
    assert decision.action == "BUY"
    assert decision.confidence == 0.85


def test_hold_signal_generates_hold_strategy():
    """A HOLD signal should produce a HOLD strategy decision."""

    signal = TradingSignal(
        symbol="RELIANCE",
        signal="HOLD",
        confidence=0.50,
        timestamp=datetime(2026, 8, 27, 9, 30),
        source="technical",
    )

    decision = generate_strategy(signal)

    assert decision.action == "HOLD"
