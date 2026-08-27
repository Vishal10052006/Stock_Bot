"""
Tests for Stock Bot signal engine.
"""

from datetime import datetime

import pytest

from features.models import FeatureSet
from signals.engine import generate_signal


TIMESTAMP = datetime(2026, 8, 27, 9, 30)


def make_features(price_change_pct: float) -> FeatureSet:
    """Create a minimal FeatureSet for signal-engine tests."""

    return FeatureSet(
        symbol="RELIANCE",
        timestamp=TIMESTAMP,
        values={
            "latest_price": 2500.0,
            "price_change_pct": price_change_pct,
            "price_range_pct": 3.0,
        },
    )


def test_positive_movement_generates_buy():
    """A price increase at or above the BUY threshold should generate BUY."""

    result = generate_signal(make_features(2.0))

    assert result.symbol == "RELIANCE"
    assert result.signal == "BUY"
    assert result.confidence == pytest.approx(0.4)
    assert result.source == "rule_based"


def test_negative_movement_generates_sell():
    """A price decrease at or below the SELL threshold should generate SELL."""

    result = generate_signal(make_features(-2.0))

    assert result.symbol == "RELIANCE"
    assert result.signal == "SELL"
    assert result.confidence == pytest.approx(0.4)
    assert result.source == "rule_based"


def test_small_movement_generates_hold():
    """A movement inside the thresholds should generate HOLD."""

    result = generate_signal(make_features(1.0))

    assert result.signal == "HOLD"
    assert result.confidence == pytest.approx(0.2)


def test_large_movement_caps_confidence():
    """Large price movements should cap confidence at 1.0."""

    result = generate_signal(make_features(10.0))

    assert result.signal == "BUY"
    assert result.confidence == 1.0


def test_missing_price_change_feature_is_rejected():
    """The signal engine requires price_change_pct."""

    features = FeatureSet(
        symbol="RELIANCE",
        timestamp=TIMESTAMP,
        values={
            "latest_price": 2500.0,
        },
    )

    with pytest.raises(ValueError, match="price_change_pct feature is required"):
        generate_signal(features)
