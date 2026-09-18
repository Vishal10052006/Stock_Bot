"""Tests for volume indicators."""

import numpy as np
import pandas as pd
import pytest

from market.indicators.volume import (
    add_volume_indicators,
    rvol,
    volume_change,
)


def make_volume(rows: int = 40) -> pd.Series:
    """Create deterministic volume data."""
    return pd.Series(
        [
            1000.0 + (index * 100.0)
            for index in range(rows)
        ],
        dtype=float,
    )


def make_ohlcv(rows: int = 40) -> pd.DataFrame:
    """Create deterministic OHLCV data."""
    close = pd.Series(
        [
            100.0 + index
            for index in range(rows)
        ],
        dtype=float,
    )

    return pd.DataFrame(
        {
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": make_volume(rows),
        }
    )


def test_rvol_warmup() -> None:
    """RVOL requires the requested number of previous candles."""
    volume = make_volume(30)

    result = rvol(
        volume,
        period=20,
    )

    assert result.iloc[:20].isna().all()
    assert result.iloc[20:].notna().all()


def test_rvol_uses_previous_volume_only() -> None:
    """The current candle must not be part of its own RVOL baseline."""
    volume = pd.Series(
        [
            100.0,
            100.0,
            100.0,
            200.0,
        ]
    )

    result = rvol(
        volume,
        period=3,
    )

    # At index 3:
    # Current volume = 200
    # Previous 3-volume average = 100
    # RVOL = 2.0
    assert result.iloc[3] == pytest.approx(2.0)


def test_rvol_normal_volume_equals_one() -> None:
    """Volume equal to its historical average should produce RVOL 1."""
    volume = pd.Series(
        [100.0] * 30
    )

    result = rvol(
        volume,
        period=20,
    )

    # Compare the complete valid RVOL region numerically.
    # Every candle has the same volume, so RVOL must equal 1.0.
    assert np.allclose(
        result.iloc[20:].to_numpy(),
        1.0,
    )


def test_rvol_increased_volume_is_above_one() -> None:
    """Above-average volume should produce RVOL above one."""
    volume = pd.Series(
        [100.0] * 20 + [250.0]
    )

    result = rvol(
        volume,
        period=20,
    )

    assert result.iloc[-1] == pytest.approx(2.5)


def test_volume_change_calculation() -> None:
    """Volume change should be expressed as a percentage."""
    volume = pd.Series(
        [
            100.0,
            150.0,
            75.0,
            75.0,
        ]
    )

    result = volume_change(
        volume,
        period=1,
    )

    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(50.0)
    assert result.iloc[2] == pytest.approx(-50.0)
    assert result.iloc[3] == pytest.approx(0.0)


def test_volume_change_custom_period() -> None:
    """Volume change should support a configurable lookback."""
    volume = pd.Series(
        [
            100.0,
            200.0,
            300.0,
            400.0,
        ]
    )

    result = volume_change(
        volume,
        period=2,
    )

    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(200.0)
    assert result.iloc[3] == pytest.approx(100.0)


def test_zero_previous_volume_produces_nan() -> None:
    """A zero historical baseline cannot produce a finite ratio."""
    volume = pd.Series(
        [
            0.0,
            100.0,
            100.0,
        ]
    )

    result = volume_change(
        volume,
        period=1,
    )

    assert np.isnan(result.iloc[1])


def test_add_volume_indicators() -> None:
    """Volume engine should add all expected columns."""
    data = make_ohlcv(40)

    result = add_volume_indicators(data)

    expected_columns = {
        "rvol_20",
        "volume_change_1",
    }

    assert expected_columns.issubset(
        result.columns
    )


def test_volume_indicators_do_not_modify_input() -> None:
    """Volume calculations must not mutate their input."""
    data = make_ohlcv(40)
    original = data.copy(deep=True)

    add_volume_indicators(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_negative_volume_is_rejected() -> None:
    """Negative volume is invalid."""
    volume = pd.Series(
        [100.0, -10.0, 200.0]
    )

    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        rvol(volume, 2)


def test_invalid_rvol_period_is_rejected() -> None:
    """RVOL period must be positive."""
    volume = make_volume()

    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        rvol(volume, 0)


def test_invalid_volume_change_period_is_rejected() -> None:
    """Volume-change period must be positive."""
    volume = make_volume()

    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        volume_change(volume, 0)
