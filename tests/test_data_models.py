"""
Tests for Stock Bot core data contracts.
"""

from datetime import datetime

import pytest

from data.models import MarketBar, SignalResult


def test_valid_market_bar():
    """A valid OHLCV bar should be accepted."""

    bar = MarketBar(
        symbol="RELIANCE",
        timestamp=datetime(2026, 8, 27, 9, 30),
        open=2500.0,
        high=2520.0,
        low=2490.0,
        close=2510.0,
        volume=100000,
    )

    assert bar.symbol == "RELIANCE"
    assert bar.close == 2510.0


def test_invalid_market_bar_prices():
    """Non-positive prices should be rejected."""

    with pytest.raises(ValueError):
        MarketBar(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            open=0,
            high=2520.0,
            low=2490.0,
            close=2510.0,
            volume=100000,
        )


def test_valid_signal_result():
    """A valid normalized signal should be accepted."""

    result = SignalResult(
        symbol="RELIANCE",
        signal="BUY",
        confidence=0.85,
        timestamp=datetime(2026, 8, 27, 9, 30),
        source="technical",
    )

    assert result.signal == "BUY"
    assert result.confidence == 0.85


def test_invalid_signal_confidence():
    """Confidence outside 0..1 should be rejected."""

    with pytest.raises(ValueError):
        SignalResult(
            symbol="RELIANCE",
            signal="BUY",
            confidence=1.5,
            timestamp=datetime(2026, 8, 27, 9, 30),
            source="technical",
        )
