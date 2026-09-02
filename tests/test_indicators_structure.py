"""Tests for price-structure indicators."""

import numpy as np
import pandas as pd
import pytest

from market.indicators.structure import (
    add_structure_indicators,
    structure_distances,
    structure_flags,
    support_resistance,
)


def make_ohlcv() -> pd.DataFrame:
    """Create deterministic OHLCV data."""
    return pd.DataFrame(
        {
            "open": [
                100.0,
                102.0,
                101.0,
                104.0,
                103.0,
                106.0,
                105.0,
                108.0,
            ],
            "high": [
                105.0,
                108.0,
                106.0,
                110.0,
                107.0,
                112.0,
                109.0,
                115.0,
            ],
            "low": [
                98.0,
                100.0,
                99.0,
                102.0,
                101.0,
                104.0,
                103.0,
                106.0,
            ],
            "close": [
                102.0,
                105.0,
                103.0,
                108.0,
                105.0,
                110.0,
                107.0,
                113.0,
            ],
            "volume": [
                1000.0,
                1100.0,
                900.0,
                1300.0,
                1000.0,
                1500.0,
                1200.0,
                1600.0,
            ],
        }
    )


def test_support_and_resistance_exclude_current_candle() -> None:
    """Current high/low must not define its own levels."""
    data = make_ohlcv()

    result = support_resistance(
        data,
        period=3,
    )

    # At index 3, use indexes 0, 1, 2 only.
    assert result.iloc[3]["support_3"] == pytest.approx(98.0)
    assert result.iloc[3]["resistance_3"] == pytest.approx(108.0)


def test_support_is_previous_rolling_low() -> None:
    """Support should equal the minimum previous low."""
    data = make_ohlcv()

    result = support_resistance(
        data,
        period=3,
    )

    # At index 5, previous lows are:
    # 99, 102, 101 -> support = 99.
    assert result.iloc[5]["support_3"] == pytest.approx(99.0)


def test_resistance_is_previous_rolling_high() -> None:
    """Resistance should equal the maximum previous high."""
    data = make_ohlcv()

    result = support_resistance(
        data,
        period=3,
    )

    # At index 5, previous highs are:
    # 106, 110, 107 -> resistance = 110.
    assert result.iloc[5]["resistance_3"] == pytest.approx(
        110.0
    )


def test_structure_warmup() -> None:
    """Support and resistance require the requested history."""
    data = make_ohlcv()

    result = support_resistance(
        data,
        period=3,
    )

    assert result.iloc[:3].isna().all().all()
    assert result.iloc[3:].notna().all().all()


def test_structure_flags() -> None:
    """Structure flags should compare current and previous candles."""
    data = make_ohlcv()

    result = structure_flags(data)

    assert result.iloc[0].isna().all()

    # Candle 1:
    # high 108 > 105 => higher high
    # low 100 > 98  => higher low
    assert result.iloc[1]["higher_high"]
    assert result.iloc[1]["higher_low"]

    # Candle 2:
    # high 106 < 108 => lower high
    # low 99 < 100  => lower low
    assert result.iloc[2]["lower_high"]
    assert result.iloc[2]["lower_low"]


def test_structure_distances() -> None:
    """Distance calculations should use causal support/resistance."""
    data = make_ohlcv()

    result = structure_distances(
        data,
        period=3,
    )

    # At index 3:
    # support = 98
    # resistance = 108
    # close = 108
    #
    # distance to support:
    # (108 - 98) / 98 * 100
    expected_support_distance = (
        (108.0 - 98.0) / 98.0 * 100.0
    )

    # Price is exactly at resistance.
    expected_resistance_distance = 0.0

    assert result.iloc[3][
        "distance_to_support_pct"
    ] == pytest.approx(
        expected_support_distance
    )

    assert result.iloc[3][
        "distance_to_resistance_pct"
    ] == pytest.approx(
        expected_resistance_distance
    )


def test_add_structure_indicators() -> None:
    """Structure engine should add all expected columns."""
    data = make_ohlcv()

    result = add_structure_indicators(
        data,
        period=3,
    )

    expected_columns = {
        "support_3",
        "resistance_3",
        "distance_to_support_pct",
        "distance_to_resistance_pct",
        "higher_high",
        "lower_low",
        "higher_low",
        "lower_high",
    }

    assert expected_columns.issubset(
        result.columns
    )


def test_structure_does_not_modify_input() -> None:
    """Structure calculations must not mutate their input."""
    data = make_ohlcv()
    original = data.copy(deep=True)

    add_structure_indicators(
        data,
        period=3,
    )

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_missing_ohlc_column_is_rejected() -> None:
    """Missing OHLC data should fail explicitly."""
    data = make_ohlcv().drop(
        columns=["high"]
    )

    with pytest.raises(
        ValueError,
        match="missing required OHLC",
    ):
        add_structure_indicators(data)


def test_invalid_period_is_rejected() -> None:
    """Structure lookback must be positive."""
    data = make_ohlcv()

    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        support_resistance(
            data,
            period=0,
        )


def test_structure_levels_are_causal() -> None:
    """Changing a future candle must not alter earlier levels."""
    data = make_ohlcv()

    original = support_resistance(
        data,
        period=3,
    )

    modified = data.copy()

    # Deliberately introduce an extreme future value.
    modified.loc[7, "high"] = 10000.0
    modified.loc[7, "low"] = 1.0

    changed = support_resistance(
        modified,
        period=3,
    )

    # The first seven observations must remain identical.
    pd.testing.assert_frame_equal(
        original.iloc[:7],
        changed.iloc[:7],
    )
