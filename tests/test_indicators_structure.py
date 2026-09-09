"""Tests for price-structure indicators."""

import numpy as np
import pandas as pd
import pytest

from market.indicators.structure import (
    add_structure_indicators,
    opening_range,
    structure_distances,
    structure_flags,
    support_resistance,
)


def make_ohlcv(rows: int = 8) -> pd.DataFrame:
    """Create deterministic OHLCV data with a configurable row count."""
    if rows <= 0:
        raise ValueError("rows must be greater than zero")

    base = pd.DataFrame(
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

    # Preserve the original fixture for existing tests while allowing
    # new tests to request longer deterministic datasets.
    repetitions = (rows + len(base) - 1) // len(base)

    return (
        pd.concat([base] * repetitions, ignore_index=True)
        .iloc[:rows]
        .reset_index(drop=True)
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


def make_two_day_ohlcv() -> pd.DataFrame:
    """Create two trading days for previous-day level tests."""
    timestamps = pd.to_datetime(
        [
            "2026-09-01 09:15:00+05:30",
            "2026-09-01 09:20:00+05:30",
            "2026-09-01 15:20:00+05:30",
            "2026-09-02 09:15:00+05:30",
            "2026-09-02 09:20:00+05:30",
            "2026-09-02 15:20:00+05:30",
        ]
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": [
                "ITC",
                "ITC",
                "ITC",
                "ITC",
                "ITC",
                "ITC",
            ],
            "open": [
                100.0,
                101.0,
                104.0,
                106.0,
                107.0,
                109.0,
            ],
            "high": [
                105.0,
                108.0,
                110.0,
                109.0,
                111.0,
                113.0,
            ],
            "low": [
                98.0,
                99.0,
                97.0,
                104.0,
                103.0,
                102.0,
            ],
            "close": [
                102.0,
                106.0,
                108.0,
                107.0,
                109.0,
                110.0,
            ],
            "volume": [
                1000.0,
                1100.0,
                1500.0,
                1200.0,
                1300.0,
                1700.0,
            ],
        }
    )


def test_previous_day_levels_use_completed_session() -> None:
    """Each day must receive the previous completed day's levels."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv()

    result = previous_day_levels(data)

    # First trading day has no previous session.
    assert result.iloc[:3]["previous_day_high"].isna().all()
    assert result.iloc[:3]["previous_day_low"].isna().all()

    # Second day uses the complete first-day range.
    assert np.allclose(
        result.iloc[3:]["previous_day_high"].to_numpy(),
        110.0,
    )

    assert np.allclose(
        result.iloc[3:]["previous_day_low"].to_numpy(),
        97.0,
    )


def test_previous_day_levels_do_not_use_current_day_extremes() -> None:
    """Today's high/low must not change today's previous-day levels."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv()

    original = previous_day_levels(data)

    modified = data.copy()

    # Extreme values belong to the current day only.
    modified.loc[3, "high"] = 10000.0
    modified.loc[3, "low"] = 1.0

    changed = previous_day_levels(modified)

    # The second day's previous-day levels must remain unchanged.
    assert changed.iloc[3]["previous_day_high"] == pytest.approx(
        original.iloc[3]["previous_day_high"]
    )

    assert changed.iloc[3]["previous_day_low"] == pytest.approx(
        original.iloc[3]["previous_day_low"]
    )


def test_previous_day_levels_are_symbol_isolated() -> None:
    """Different symbols must not share previous-day levels."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv()

    extra = data.copy()

    extra["symbol"] = [
        "ITC",
        "ITC",
        "ITC",
        "RELIANCE",
        "RELIANCE",
        "RELIANCE",
    ]

    result = previous_day_levels(extra)

    # RELIANCE has no previous-day candles in this test dataset.
    assert result.iloc[3:]["previous_day_high"].isna().all()
    assert result.iloc[3:]["previous_day_low"].isna().all()


def test_previous_day_levels_require_timestamp() -> None:
    """Previous-day levels require an explicit timestamp column."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv().drop(
        columns=["timestamp"]
    )

    with pytest.raises(
        ValueError,
        match="missing required timestamp",
    ):
        previous_day_levels(data)


def test_previous_day_levels_reject_naive_timestamp() -> None:
    """Session boundaries require timezone-aware timestamps."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv()

    data["timestamp"] = (
        data["timestamp"]
        .dt.tz_localize(None)
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        previous_day_levels(data)


def test_previous_day_levels_preserve_input() -> None:
    """Previous-day calculations must not mutate input data."""
    from market.indicators.structure import previous_day_levels

    data = make_two_day_ohlcv()
    original = data.copy(deep=True)

    previous_day_levels(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_previous_day_levels_integrate_into_structure_engine() -> None:
    """Unified structure output should expose previous-day levels."""
    data = make_two_day_ohlcv()

    result = add_structure_indicators(
        data,
        period=2,
    )

    assert "previous_day_high" in result.columns
    assert "previous_day_low" in result.columns

    assert result.iloc[3]["previous_day_high"] == pytest.approx(
        110.0
    )

    assert result.iloc[3]["previous_day_low"] == pytest.approx(
        97.0
    )


def make_opening_range_ohlcv() -> pd.DataFrame:
    """Create deterministic NSE-style five-minute candles."""
    timestamps = pd.to_datetime(
        [
            "2026-09-01 09:15:00+05:30",
            "2026-09-01 09:20:00+05:30",
            "2026-09-01 09:25:00+05:30",
            "2026-09-01 09:30:00+05:30",
            "2026-09-01 09:35:00+05:30",
        ]
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * 5,
            "open": [
                100.0,
                102.0,
                101.0,
                104.0,
                106.0,
            ],
            "high": [
                105.0,
                108.0,
                106.0,
                110.0,
                112.0,
            ],
            "low": [
                98.0,
                100.0,
                99.0,
                103.0,
                105.0,
            ],
            "close": [
                102.0,
                106.0,
                104.0,
                108.0,
                111.0,
            ],
            "volume": [
                1000.0,
                1200.0,
                1100.0,
                1400.0,
                1500.0,
            ],
        }
    )


def test_opening_range_is_unavailable_before_completion() -> None:
    """Opening-range levels must not exist before 09:30."""
    data = make_opening_range_ohlcv()

    result = opening_range(data)

    assert result.iloc[:3].isna().all().all()


def test_opening_range_uses_first_fifteen_minutes() -> None:
    """09:15, 09:20 and 09:25 candles define the range."""
    data = make_opening_range_ohlcv()

    result = opening_range(data)

    # Opening highs: 105, 108, 106 -> 108.
    assert result.iloc[3]["opening_range_high"] == pytest.approx(
        108.0
    )

    # Opening lows: 98, 100, 99 -> 98.
    assert result.iloc[3]["opening_range_low"] == pytest.approx(
        98.0
    )

    assert result.iloc[3]["opening_range_width"] == pytest.approx(
        10.0
    )


def test_opening_range_remains_constant_after_completion() -> None:
    """Later candles must not redefine the opening range."""
    data = make_opening_range_ohlcv()

    result = opening_range(data)

    assert result.iloc[4]["opening_range_high"] == pytest.approx(
        108.0
    )

    assert result.iloc[4]["opening_range_low"] == pytest.approx(
        98.0
    )


def test_opening_range_is_causal() -> None:
    """Future candles must not alter an already completed range."""
    data = make_opening_range_ohlcv()

    original = opening_range(data)

    modified = data.copy()

    # Extreme values occur after the opening range.
    modified.loc[4, "high"] = 10000.0
    modified.loc[4, "low"] = 1.0

    changed = opening_range(modified)

    assert changed.iloc[3]["opening_range_high"] == pytest.approx(
        original.iloc[3]["opening_range_high"]
    )

    assert changed.iloc[3]["opening_range_low"] == pytest.approx(
        original.iloc[3]["opening_range_low"]
    )


def test_opening_range_is_symbol_isolated() -> None:
    """Opening ranges must be calculated independently per symbol."""
    data = make_opening_range_ohlcv()

    second_symbol = data.copy()

    second_symbol["symbol"] = [
        "ITC",
        "ITC",
        "ITC",
        "RELIANCE",
        "RELIANCE",
    ]

    result = opening_range(second_symbol)

    # RELIANCE has no opening-range candles in this dataset.
    assert result.iloc[3:]["opening_range_high"].isna().all()
    assert result.iloc[3:]["opening_range_low"].isna().all()


def test_opening_range_requires_timestamp() -> None:
    """Opening-range calculation requires session timestamps."""
    data = make_opening_range_ohlcv().drop(
        columns=["timestamp"]
    )

    with pytest.raises(
        ValueError,
        match="missing required timestamp",
    ):
        opening_range(data)


def test_opening_range_rejects_naive_timestamp() -> None:
    """Session-aware opening range requires timezone-aware timestamps."""
    data = make_opening_range_ohlcv()

    data["timestamp"] = (
        data["timestamp"]
        .dt.tz_localize(None)
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        opening_range(data)


def test_opening_range_integrates_into_structure_engine() -> None:
    """Unified structure output should expose opening-range levels."""
    data = make_opening_range_ohlcv()

    result = add_structure_indicators(
        data,
        period=2,
    )

    assert "opening_range_high" in result.columns
    assert "opening_range_low" in result.columns
    assert "opening_range_width" in result.columns

    assert result.iloc[3]["opening_range_high"] == pytest.approx(
        108.0
    )

    assert result.iloc[3]["opening_range_low"] == pytest.approx(
        98.0
    )

    assert result.iloc[3]["opening_range_width"] == pytest.approx(
        10.0
    )


def make_swing_ohlcv() -> pd.DataFrame:
    """Create deterministic data containing confirmed swing points."""
    return pd.DataFrame(
        {
            "open": [
                100.0,
                102.0,
                105.0,
                103.0,
                101.0,
                102.0,
                104.0,
                103.0,
                101.0,
            ],
            "high": [
                101.0,
                104.0,
                110.0,
                105.0,
                103.0,
                106.0,
                108.0,
                105.0,
                103.0,
            ],
            "low": [
                99.0,
                101.0,
                104.0,
                102.0,
                98.0,
                100.0,
                103.0,
                101.0,
                99.0,
            ],
            "close": [
                100.0,
                103.0,
                107.0,
                104.0,
                100.0,
                104.0,
                106.0,
                103.0,
                101.0,
            ],
            "volume": [
                1000.0,
                1100.0,
                1500.0,
                1200.0,
                1400.0,
                1300.0,
                1600.0,
                1200.0,
                1100.0,
            ],
        }
    )


def test_swing_high_is_confirmed_after_right_bars() -> None:
    """Swing highs must only appear after right-side confirmation."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    result = swing_levels(
        data,
        left_bars=2,
        right_bars=2,
    )

    # Index 2 is the swing high:
    # 110 > 101, 104 on the left
    # 110 > 105, 103 on the right
    #
    # It becomes known at index 4.
    assert pd.isna(result.iloc[2]["swing_high"])
    assert pd.isna(result.iloc[3]["swing_high"])
    assert result.iloc[4]["swing_high"] == pytest.approx(
        110.0
    )


def test_swing_low_is_confirmed_after_right_bars() -> None:
    """Swing lows must only appear after right-side confirmation."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    result = swing_levels(
        data,
        left_bars=2,
        right_bars=2,
    )

    # Index 4 is a swing low:
    # 98 < 99, 101 on the left
    # 98 < 100, 103 on the right
    #
    # It becomes known at index 6.
    assert pd.isna(result.iloc[4]["swing_low"])
    assert pd.isna(result.iloc[5]["swing_low"])
    assert result.iloc[6]["swing_low"] == pytest.approx(
        98.0
    )


def test_swing_levels_carry_latest_confirmed_level() -> None:
    """Confirmed swing levels remain available until replaced."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    result = swing_levels(
        data,
        left_bars=2,
        right_bars=2,
    )

    assert result.iloc[4]["swing_high"] == pytest.approx(
        110.0
    )

    assert result.iloc[5]["swing_high"] == pytest.approx(
        110.0
    )

    assert result.iloc[6]["swing_high"] == pytest.approx(
        110.0
    )


def test_swing_levels_are_causal() -> None:
    """Future modifications must not alter earlier confirmations."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    original = swing_levels(
        data,
        left_bars=2,
        right_bars=2,
    )

    modified = data.copy()

    # Modify a candle after an already-confirmed swing.
    modified.loc[8, "high"] = 10000.0
    modified.loc[8, "low"] = 1.0

    changed = swing_levels(
        modified,
        left_bars=2,
        right_bars=2,
    )

    pd.testing.assert_frame_equal(
        original.iloc[:8],
        changed.iloc[:8],
    )


def test_swing_levels_are_symbol_isolated() -> None:
    """Swing calculations must not cross symbol boundaries."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    data["symbol"] = [
        "ITC",
        "ITC",
        "ITC",
        "ITC",
        "ITC",
        "RELIANCE",
        "RELIANCE",
        "RELIANCE",
        "RELIANCE",
    ]

    result = swing_levels(
        data,
        left_bars=2,
        right_bars=2,
    )

    # RELIANCE does not have enough preceding candles to confirm
    # the ITC swing at index 4.
    assert pd.isna(
        result.iloc[5]["swing_high"]
    )


def test_swing_levels_validate_bar_parameters() -> None:
    """Swing confirmation windows must be positive."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()

    with pytest.raises(
        ValueError,
        match="left_bars must be greater than zero",
    ):
        swing_levels(
            data,
            left_bars=0,
        )

    with pytest.raises(
        ValueError,
        match="right_bars must be greater than zero",
    ):
        swing_levels(
            data,
            right_bars=0,
        )


def test_swing_levels_do_not_modify_input() -> None:
    """Swing calculations must not mutate the input DataFrame."""
    from market.indicators.structure import swing_levels

    data = make_swing_ohlcv()
    original = data.copy(deep=True)

    swing_levels(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_swing_levels_integrate_into_structure_engine() -> None:
    """Unified structure output should expose swing levels."""
    data = make_swing_ohlcv()

    result = add_structure_indicators(
        data,
        period=2,
    )

    assert "swing_high" in result.columns
    assert "swing_low" in result.columns

    assert result.iloc[4]["swing_high"] == pytest.approx(
        110.0
    )

    assert result.iloc[6]["swing_low"] == pytest.approx(
        98.0
    )


def test_breakouts_detect_upward_breakout() -> None:
    """A close above previous resistance is an upward breakout."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(6)

    data.loc[data.index[:5], "high"] = [
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
    ]
    data.loc[data.index[:5], "low"] = [
        98.0,
        99.0,
        100.0,
        101.0,
        102.0,
    ]
    data.loc[data.index[5], "close"] = 106.0

    result = breakouts(data, period=5)

    assert bool(result.iloc[5]["breakout_up"]) is True
    assert bool(result.iloc[5]["breakout_down"]) is False
    assert result.iloc[5]["breakout_distance_pct"] == pytest.approx(
        (106.0 - 105.0) / 105.0 * 100.0
    )


def test_breakouts_detect_downward_breakout() -> None:
    """A close below previous support is a downward breakout."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(6)

    data.loc[data.index[:5], "high"] = [
        102.0,
        103.0,
        104.0,
        105.0,
        106.0,
    ]
    data.loc[data.index[:5], "low"] = [
        99.0,
        98.0,
        97.0,
        96.0,
        95.0,
    ]
    data.loc[data.index[5], "close"] = 94.0

    result = breakouts(data, period=5)

    assert bool(result.iloc[5]["breakout_up"]) is False
    assert bool(result.iloc[5]["breakout_down"]) is True
    assert result.iloc[5]["breakout_distance_pct"] == pytest.approx(
        -(94.0 - 95.0) / 95.0 * 100.0
    )


def test_breakouts_do_not_use_current_candle_to_define_level() -> None:
    """The current candle cannot manufacture its own breakout level."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(6)

    data.loc[data.index[:5], "high"] = 105.0
    data.loc[data.index[:5], "low"] = 95.0

    # Current high is extreme, but close remains below the previous
    # resistance. The current high must not become the reference.
    data.loc[data.index[5], "high"] = 1000.0
    data.loc[data.index[5], "close"] = 104.0

    result = breakouts(data, period=5)

    assert bool(result.iloc[5]["breakout_up"]) is False
    assert bool(result.iloc[5]["breakout_down"]) is False


def test_breakouts_require_completed_reference_window() -> None:
    """Breakout flags remain unavailable before the lookback is complete."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(5)
    result = breakouts(data, period=5)

    assert result.iloc[:5]["breakout_up"].isna().all()
    assert result.iloc[:5]["breakout_down"].isna().all()


def test_breakouts_validate_period() -> None:
    """Breakout lookback period must be positive."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(10)

    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        breakouts(data, period=0)


def test_breakouts_do_not_modify_input() -> None:
    """Breakout calculation must not mutate the input DataFrame."""
    from market.indicators.structure import breakouts

    data = make_ohlcv(30)
    original = data.copy(deep=True)

    breakouts(data, period=5)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_retests_detect_bullish_retest() -> None:
    """A later candle touching broken resistance and closing above it is a bullish retest."""
    from market.indicators.structure import retests

    data = make_ohlcv(7)

    # Five-candle resistance = 105.
    data.loc[data.index[:5], "high"] = 105.0
    data.loc[data.index[:5], "low"] = 95.0

    # Candle 5 breaks above resistance.
    data.loc[data.index[5], "close"] = 108.0
    data.loc[data.index[5], "high"] = 109.0

    # Candle 6 retests 105 and closes back above it.
    data.loc[data.index[6], "low"] = 104.5
    data.loc[data.index[6], "close"] = 106.0

    result = retests(data, period=5)

    assert bool(result.iloc[6]["retest_up"]) is True
    assert bool(result.iloc[6]["retest_down"]) is False
    assert result.iloc[6]["retest_level"] == pytest.approx(105.0)


def test_retests_detect_bearish_retest() -> None:
    """A later candle touching broken support and closing below it is a bearish retest."""
    from market.indicators.structure import retests

    data = make_ohlcv(7)

    # Five-candle support = 95.
    data.loc[data.index[:5], "high"] = 105.0
    data.loc[data.index[:5], "low"] = 95.0

    # Candle 5 breaks below support.
    data.loc[data.index[5], "close"] = 92.0
    data.loc[data.index[5], "low"] = 91.0

    # Candle 6 retests 95 and closes back below it.
    data.loc[data.index[6], "high"] = 95.5
    data.loc[data.index[6], "close"] = 93.0

    result = retests(data, period=5)

    assert bool(result.iloc[6]["retest_up"]) is False
    assert bool(result.iloc[6]["retest_down"]) is True
    assert result.iloc[6]["retest_level"] == pytest.approx(95.0)


def test_retests_cannot_trigger_on_breakout_candle() -> None:
    """The breakout candle cannot simultaneously be its own retest."""
    from market.indicators.structure import retests

    data = make_ohlcv(6)

    data.loc[data.index[:5], "high"] = 105.0
    data.loc[data.index[:5], "low"] = 95.0

    data.loc[data.index[5], "high"] = 110.0
    data.loc[data.index[5], "low"] = 104.0
    data.loc[data.index[5], "close"] = 108.0

    result = retests(data, period=5)

    assert bool(result.iloc[5]["retest_up"]) is False


def test_retests_require_completed_reference_window() -> None:
    """Retests remain unavailable before the breakout reference window exists."""
    from market.indicators.structure import retests

    data = make_ohlcv(5)
    result = retests(data, period=5)

    assert result.iloc[:5]["retest_up"].isna().all()
    assert result.iloc[:5]["retest_down"].isna().all()


def test_retests_validate_period() -> None:
    """Retest lookback period must be positive."""
    from market.indicators.structure import retests

    data = make_ohlcv(10)

    with pytest.raises(
        ValueError,
        match="period must be greater than zero",
    ):
        retests(data, period=0)


def test_vwap_distance_is_zero_when_close_equals_vwap() -> None:
    """VWAP distance must be zero when close equals session VWAP."""
    from market.indicators.structure import vwap_distance

    data = make_ohlcv().copy()

    data["timestamp"] = pd.date_range(
        "2026-01-01 09:15",
        periods=len(data),
        freq="min",
        tz="Asia/Kolkata",
    )

    result = vwap_distance(data)

    # Force the final candle's OHLC to the same value so the final
    # typical price and close equal the cumulative VWAP only when
    # all preceding prices are also aligned.
    aligned = data.copy()
    aligned["open"] = 100.0
    aligned["high"] = 100.0
    aligned["low"] = 100.0
    aligned["close"] = 100.0

    result = vwap_distance(aligned)

    assert result.iloc[-1]["vwap_distance_pct"] == pytest.approx(0.0)


def test_vwap_distance_is_positive_above_vwap() -> None:
    """Close above VWAP must produce a positive distance."""
    from market.indicators.structure import vwap_distance

    data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:15",
                periods=2,
                freq="min",
                tz="Asia/Kolkata",
            ),
            "open": [100.0, 110.0],
            "high": [100.0, 110.0],
            "low": [100.0, 110.0],
            "close": [100.0, 110.0],
            "volume": [1000.0, 1000.0],
        }
    )

    result = vwap_distance(data)

    assert result.iloc[1]["vwap_distance_pct"] > 0.0


def test_vwap_distance_is_negative_below_vwap() -> None:
    """Close below VWAP must produce a negative distance."""
    from market.indicators.structure import vwap_distance

    data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:15",
                periods=2,
                freq="min",
                tz="Asia/Kolkata",
            ),
            "open": [110.0, 100.0],
            "high": [110.0, 100.0],
            "low": [110.0, 100.0],
            "close": [110.0, 100.0],
            "volume": [1000.0, 1000.0],
        }
    )

    result = vwap_distance(data)

    assert result.iloc[1]["vwap_distance_pct"] < 0.0


def test_vwap_distance_requires_timestamp() -> None:
    """VWAP distance requires a session timestamp."""
    from market.indicators.structure import vwap_distance

    data = make_ohlcv()

    with pytest.raises(
        ValueError,
        match="missing required columns",
    ):
        vwap_distance(data)
