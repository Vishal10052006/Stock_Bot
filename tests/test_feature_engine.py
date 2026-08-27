"""
Tests for Stock Bot feature engine.
"""

from datetime import datetime

import pytest

from features.engine import calculate_features


def test_calculate_features():
    """Feature values should be calculated correctly."""

    result = calculate_features(
        symbol="RELIANCE",
        prices=[100.0, 105.0, 110.0],
        timestamp=datetime(2026, 8, 27, 9, 30),
    )

    assert result.symbol == "RELIANCE"
    assert result.values["latest_price"] == 110.0
    assert result.values["price_change_pct"] == 10.0
    assert result.values["price_range_pct"] == 10.0


def test_declining_prices_produce_negative_change():
    """A declining price series should produce negative change."""

    result = calculate_features(
        symbol="RELIANCE",
        prices=[100.0, 95.0, 90.0],
        timestamp=datetime(2026, 8, 27, 9, 30),
    )

    assert result.values["latest_price"] == 90.0
    assert result.values["price_change_pct"] == -10.0
    assert result.values["price_range_pct"] == pytest.approx(11.1111111111)


def test_empty_prices_are_rejected():
    """An empty price sequence should be rejected."""

    with pytest.raises(ValueError):
        calculate_features(
            symbol="RELIANCE",
            prices=[],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_non_positive_prices_are_rejected():
    """Zero or negative prices should be rejected."""

    with pytest.raises(ValueError):
        calculate_features(
            symbol="RELIANCE",
            prices=[100.0, 0.0, 110.0],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_empty_symbol_is_rejected():
    """An empty symbol should be rejected."""

    with pytest.raises(ValueError):
        calculate_features(
            symbol="",
            prices=[100.0, 105.0, 110.0],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_non_numeric_prices_are_rejected():
    """Non-numeric price values should be rejected."""

    with pytest.raises(
        ValueError,
        match="prices must be numeric",
    ):
        calculate_features(
            symbol="RELIANCE",
            prices=[100.0, "invalid", 110.0],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_non_finite_prices_are_rejected():
    """NaN and infinite prices should be rejected."""

    with pytest.raises(
        ValueError,
        match="prices must be finite",
    ):
        calculate_features(
            symbol="RELIANCE",
            prices=[100.0, float("nan"), 110.0],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )


def test_infinite_prices_are_rejected():
    """Infinite prices should be rejected."""

    with pytest.raises(
        ValueError,
        match="prices must be finite",
    ):
        calculate_features(
            symbol="RELIANCE",
            prices=[100.0, float("inf"), 110.0],
            timestamp=datetime(2026, 8, 27, 9, 30),
        )
