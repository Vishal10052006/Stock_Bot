"""Tests for volatility indicators."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from market.indicators.volatility import (
    add_volatility_indicators,
    atr,
    bollinger_bands,
    realized_volatility,
    true_range,
)


IST = ZoneInfo("Asia/Kolkata")


def make_ohlcv(rows: int = 60) -> pd.DataFrame:
    """Create deterministic OHLCV data."""
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


def test_true_range_first_row_uses_high_low() -> None:
    """The first True Range has no previous close."""
    data = make_ohlcv(3)

    result = true_range(data)

    assert result.iloc[0] == pytest.approx(
        data.iloc[0]["high"]
        - data.iloc[0]["low"]
    )


def test_true_range_uses_previous_close() -> None:
    """True Range must account for gaps from the previous close."""
    data = pd.DataFrame(
        {
            "high": [105.0, 115.0],
            "low": [95.0, 110.0],
            "close": [100.0, 112.0],
        }
    )

    result = true_range(data)

    # Second row:
    # high-low = 5
    # |high-prev_close| = 15
    # |low-prev_close| = 10
    # therefore TR = 15.
    assert result.iloc[1] == pytest.approx(15.0)


def test_atr_warmup() -> None:
    """ATR should require the requested number of observations."""
    data = make_ohlcv(30)

    result = atr(data, 14)

    assert result.iloc[:13].isna().all()
    assert result.iloc[13:].notna().all()


def test_atr_is_positive() -> None:
    """ATR should be positive for non-flat OHLC data."""
    data = make_ohlcv(30)

    result = atr(data, 14).dropna()

    assert (result > 0).all()


def test_bollinger_bands_warmup() -> None:
    """Bollinger Bands require the requested rolling window."""
    close = make_ohlcv(30)["close"]

    result = bollinger_bands(close, 20)

    assert result.iloc[:19].isna().all().all()
    assert result.iloc[19:].notna().all().all()


def test_bollinger_band_order() -> None:
    """Upper band must be above middle and lower."""
    close = make_ohlcv(40)["close"]

    result = bollinger_bands(close, 20)

    valid = result.dropna()

    assert (
        valid["bb_upper"]
        >= valid["bb_middle"]
    ).all()

    assert (
        valid["bb_middle"]
        >= valid["bb_lower"]
    ).all()


def test_bollinger_width_formula() -> None:
    """Band width must equal normalized band spread."""
    close = make_ohlcv(30)["close"]

    result = bollinger_bands(close, 20)

    valid = result.dropna()

    expected = (
        (valid["bb_upper"] - valid["bb_lower"])
        / valid["bb_middle"]
    )

    pd.testing.assert_series_equal(
        valid["bb_width"],
        expected,
        check_names=False,
    )


def test_realized_volatility_warmup() -> None:
    """Realized volatility requires the requested number of returns."""
    close = make_ohlcv(40)["close"]

    result = realized_volatility(
        close,
        period=20,
    )

    # One observation is consumed by diff/log-return,
    # therefore the first 20 rows remain unavailable.
    assert result.iloc[:20].isna().all()
    assert result.iloc[20:].notna().all()


def test_realized_volatility_is_non_negative() -> None:
    """Volatility cannot be negative."""
    close = make_ohlcv(40)["close"]

    result = realized_volatility(
        close,
        period=20,
    ).dropna()

    assert (result >= 0.0).all()


def test_annualized_volatility_scales_correctly() -> None:
    """Annualization should multiply volatility by sqrt(factor)."""
    close = make_ohlcv(50)["close"]

    raw = realized_volatility(
        close,
        period=20,
    )

    annualized = realized_volatility(
        close,
        period=20,
        annualization_factor=100.0,
    )

    valid = raw.notna()

    np.testing.assert_allclose(
        annualized[valid].to_numpy(),
        raw[valid].to_numpy() * 10.0,
    )


def test_add_volatility_indicators() -> None:
    """The volatility engine should add every expected column."""
    data = make_ohlcv(60)

    result = add_volatility_indicators(data)

    expected_columns = {
        "atr_14",
        "bb_middle",
        "bb_upper",
        "bb_lower",
        "bb_width",
        "realized_volatility_20",
    }

    assert expected_columns.issubset(
        result.columns
    )


def test_volatility_does_not_modify_input() -> None:
    """Volatility calculations must not mutate their input."""
    data = make_ohlcv(60)
    original = data.copy(deep=True)

    add_volatility_indicators(data)

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_invalid_close_is_rejected() -> None:
    """Non-positive close prices cannot produce log returns."""
    close = pd.Series(
        [100.0, 0.0, 101.0]
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        realized_volatility(close, 2)


def test_invalid_bollinger_standard_deviation_is_rejected() -> None:
    """Bollinger standard deviation multiplier must be positive."""
    close = make_ohlcv(30)["close"]

    with pytest.raises(
        ValueError,
        match="standard_deviations",
    ):
        bollinger_bands(
            close,
            period=20,
            standard_deviations=0,
        )
