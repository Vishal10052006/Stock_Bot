"""Tests for trend indicators."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from market.indicators.trend import (
    add_trend_indicators,
    ema,
    sma,
    vwap,
)


IST = ZoneInfo("Asia/Kolkata")


def make_ohlcv(rows: int = 60) -> pd.DataFrame:
    """Create deterministic intraday OHLCV test data."""
    timestamps = [
        datetime(
            2026,
            9,
            1,
            9,
            15,
            tzinfo=IST,
        ) + timedelta(minutes=5 * index)
        for index in range(rows)
    ]

    close = pd.Series(
        [100.0 + index for index in range(rows)],
        dtype=float,
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        }
    )


def test_ema_has_expected_warmup() -> None:
    """EMA should remain NaN until its requested period is available."""
    close = pd.Series(
        [float(value) for value in range(1, 11)]
    )

    result = ema(close, 5)

    assert result.iloc[:4].isna().all()
    assert result.iloc[4:].notna().all()


def test_ema_is_deterministic() -> None:
    """The same input must always produce the same EMA."""
    close = pd.Series(
        [100.0, 101.0, 102.0, 103.0, 104.0]
    )

    first = ema(close, 3)
    second = ema(close, 3)

    pd.testing.assert_series_equal(
        first,
        second,
    )


def test_sma_calculation() -> None:
    """SMA should equal the arithmetic rolling mean."""
    close = pd.Series(
        [1.0, 2.0, 3.0, 4.0, 5.0]
    )

    result = sma(close, 3)

    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_vwap_calculation() -> None:
    """VWAP should use typical price weighted by volume."""
    data = pd.DataFrame(
        {
            "timestamp": [
                datetime(
                    2026,
                    9,
                    1,
                    9,
                    15,
                    tzinfo=IST,
                ),
                datetime(
                    2026,
                    9,
                    1,
                    9,
                    20,
                    tzinfo=IST,
                ),
            ],
            "open": [99.0, 101.0],
            "high": [102.0, 104.0],
            "low": [98.0, 100.0],
            "close": [101.0, 103.0],
            "volume": [100.0, 300.0],
        }
    )

    result = vwap(data)

    typical_price_1 = (102.0 + 98.0 + 101.0) / 3.0
    typical_price_2 = (104.0 + 100.0 + 103.0) / 3.0

    expected_first = typical_price_1
    expected_second = (
        typical_price_1 * 100.0
        + typical_price_2 * 300.0
    ) / 400.0

    assert result.iloc[0] == pytest.approx(
        expected_first
    )

    assert result.iloc[1] == pytest.approx(
        expected_second
    )


def test_vwap_resets_each_session() -> None:
    """VWAP must not carry volume from one trading day into another."""
    data = make_ohlcv(2)

    next_day = data.copy()
    next_day["timestamp"] = [
        timestamp + timedelta(days=1)
        for timestamp in data["timestamp"]
    ]

    combined = pd.concat(
        [data, next_day],
        ignore_index=True,
    )

    result = vwap(combined)

    # First candle of the second session should equal
    # that candle's own typical price.
    second_session_row = combined.iloc[2]

    expected = (
        second_session_row["high"]
        + second_session_row["low"]
        + second_session_row["close"]
    ) / 3.0

    assert result.iloc[2] == pytest.approx(expected)


def test_add_trend_indicators_adds_expected_columns() -> None:
    """Trend engine should add all required trend columns."""
    data = make_ohlcv(60)

    result = add_trend_indicators(data)

    expected_columns = {
        "ema_9",
        "ema_20",
        "ema_50",
        "sma",
        "vwap",
    }

    assert expected_columns.issubset(result.columns)

    assert result["ema_9"].notna().sum() == 52
    assert result["ema_20"].notna().sum() == 41
    assert result["ema_50"].notna().sum() == 11


def test_original_dataframe_is_not_modified() -> None:
    """Indicator calculation must not mutate its input."""
    data = make_ohlcv(60)
    original = data.copy(deep=True)

    add_trend_indicators(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_missing_ohlcv_column_is_rejected() -> None:
    """Missing OHLCV columns should fail explicitly."""
    data = make_ohlcv(10).drop(columns=["volume"])

    with pytest.raises(ValueError, match="missing required"):
        add_trend_indicators(data)
