"""
Tests for Stock Bot signal data contracts.
"""

from datetime import datetime

import pytest

from signals.models import TradingSignal


def test_valid_trading_signal():
    """A valid trading signal should be accepted."""

    signal = TradingSignal(
        symbol="RELIANCE",
        signal="BUY",
        confidence=0.85,
        timestamp=datetime(2026, 8, 27, 9, 30),
        source="technical",
    )

    assert signal.symbol == "RELIANCE"
    assert signal.signal == "BUY"
    assert signal.confidence == 0.85


def test_invalid_signal_type_is_rejected():
    """Unsupported signal types should be rejected."""

    with pytest.raises(ValueError):
        TradingSignal(
            symbol="RELIANCE",
            signal="INVALID",
            confidence=0.85,
            timestamp=datetime(2026, 8, 27, 9, 30),
            source="technical",
        )


def test_invalid_confidence_is_rejected():
    """Confidence outside 0..1 should be rejected."""

    with pytest.raises(ValueError):
        TradingSignal(
            symbol="RELIANCE",
            signal="BUY",
            confidence=1.5,
            timestamp=datetime(2026, 8, 27, 9, 30),
            source="technical",
        )


def test_nan_confidence_is_rejected():
    """NaN confidence values should be rejected."""

    with pytest.raises(
        ValueError,
        match="confidence must be finite",
    ):
        TradingSignal(
            symbol="RELIANCE",
            signal="BUY",
            confidence=float("nan"),
            timestamp=datetime(2026, 8, 27, 9, 30),
            source="technical",
        )


def test_infinite_confidence_is_rejected():
    """Infinite confidence values should be rejected."""

    with pytest.raises(
        ValueError,
        match="confidence must be finite",
    ):
        TradingSignal(
            symbol="RELIANCE",
            signal="BUY",
            confidence=float("inf"),
            timestamp=datetime(2026, 8, 27, 9, 30),
            source="technical",
        )
