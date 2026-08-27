"""
Tests for Stock Bot feature data contracts.
"""

from datetime import datetime

import pytest

from features.models import FeatureSet


def test_valid_feature_set():
    """A valid feature set should be accepted."""

    features = FeatureSet(
        symbol="RELIANCE",
        timestamp=datetime(2026, 8, 27, 9, 30),
        values={
            "rsi": 55.0,
            "sma_20": 2500.0,
            "volume_ratio": 1.2,
        },
    )

    assert features.symbol == "RELIANCE"
    assert features.values["rsi"] == 55.0


def test_empty_feature_values_are_rejected():
    """An empty feature collection should be rejected."""

    with pytest.raises(ValueError):
        FeatureSet(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            values={},
        )


def test_non_numeric_feature_is_rejected():
    """Feature values must be numeric."""

    with pytest.raises(ValueError):
        FeatureSet(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            values={
                "rsi": "high",
            },
        )


def test_nan_feature_is_rejected():
    """NaN feature values should be rejected."""

    with pytest.raises(
        ValueError,
        match="feature values must be finite",
    ):
        FeatureSet(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            values={
                "rsi": float("nan"),
            },
        )


def test_positive_infinity_feature_is_rejected():
    """Positive infinity should be rejected."""

    with pytest.raises(
        ValueError,
        match="feature values must be finite",
    ):
        FeatureSet(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            values={
                "rsi": float("inf"),
            },
        )


def test_negative_infinity_feature_is_rejected():
    """Negative infinity should be rejected."""

    with pytest.raises(
        ValueError,
        match="feature values must be finite",
    ):
        FeatureSet(
            symbol="RELIANCE",
            timestamp=datetime(2026, 8, 27, 9, 30),
            values={
                "rsi": float("-inf"),
            },
        )
