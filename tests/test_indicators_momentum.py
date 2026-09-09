"""Tests for momentum indicators."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from market.indicators.momentum import (
    add_momentum_indicators,
    macd,
    roc,
    rsi,
)


IST = ZoneInfo("Asia/Kolkata")


def make_close(rows: int = 60) -> pd.Series:
    """Create deterministic close prices."""
    return pd.Series(
        [
            100.0 + (index * 0.5)
            for index in range(rows)
        ],
        dtype=float,
    )


def make_ohlcv(rows: int = 60) -> pd.DataFrame:
    """Create deterministic OHLCV data."""
    close = make_close(rows)

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

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": close - 0.25,
            "high": close + 0.75,
            "low": close - 0.75,
            "close": close,
            "volume": 1000.0,
        }
    )


def test_rsi_warmup() -> None:
    """RSI should require the requested number of price changes."""
    close = make_close(30)

    result = rsi(close, 14)

    assert result.iloc[:14].isna().all()
    assert result.iloc[14:].notna().all()


def test_rsi_is_bounded() -> None:
    """RSI must remain between 0 and 100."""
    result = rsi(make_close(60), 14)

    valid = result.dropna()

    assert (valid >= 0.0).all()
    assert (valid <= 100.0).all()


def test_rsi_flat_market_is_50() -> None:
    """A flat market should produce RSI of 50."""
    close = pd.Series([100.0] * 30)

    result = rsi(close, 14)

    assert result.iloc[14] == pytest.approx(50.0)


def test_rsi_rising_market_reaches_100() -> None:
    """A market with only gains should produce RSI of 100."""
    close = pd.Series(
        [100.0 + index for index in range(30)]
    )

    result = rsi(close, 14)

    assert result.iloc[-1] == pytest.approx(100.0)


def test_macd_has_expected_columns() -> None:
    """MACD should expose line, signal, and histogram."""
    result = macd(make_close(60))

    assert list(result.columns) == [
        "macd",
        "macd_signal",
        "macd_histogram",
    ]


def test_macd_histogram_is_difference() -> None:
    """Histogram must equal MACD line minus signal line."""
    result = macd(make_close(60))

    valid = result.dropna()

    expected = (
        valid["macd"]
        - valid["macd_signal"]
    )

    pd.testing.assert_series_equal(
        valid["macd_histogram"],
        expected,
        check_names=False,
    )


def test_macd_warmup() -> None:
    """MACD should respect slow and signal-period warm-up."""
    result = macd(make_close(60))

    assert result["macd"].iloc[:25].isna().all()
    assert result["macd"].iloc[26:].notna().all()

    # The signal line needs additional observations after
    # the first valid MACD value.
    assert result["macd_signal"].notna().sum() > 0


def test_roc_calculation() -> None:
    """ROC should calculate percentage price change."""
    close = pd.Series(
        [100.0, 110.0, 120.0, 130.0]
    )

    result = roc(close, 2)

    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(20.0)
    assert result.iloc[3] == pytest.approx(
        (130.0 / 110.0 - 1.0) * 100.0
    )


def test_add_momentum_indicators() -> None:
    """Momentum engine should add all expected columns."""
    data = make_ohlcv(60)

    result = add_momentum_indicators(data)

    expected_columns = {
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "roc_14",
    }

    assert expected_columns.issubset(result.columns)


def test_momentum_does_not_modify_input() -> None:
    """Momentum calculation must not mutate its input."""
    data = make_ohlcv(60)
    original = data.copy(deep=True)

    add_momentum_indicators(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_invalid_macd_periods_are_rejected() -> None:
    """Fast MACD period must be smaller than slow period."""
    with pytest.raises(
        ValueError,
        match="fast_period must be less than slow_period",
    ):
        macd(
            make_close(60),
            fast_period=26,
            slow_period=12,
        )
