"""Volatility indicators for OHLCV market data.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_ohlc(data: pd.DataFrame) -> None:
    """Validate the OHLC columns required by volatility indicators."""
    required = {"high", "low", "close"}
    missing = required.difference(data.columns)

    if missing:
        raise ValueError(
            f"missing required OHLC columns: {sorted(missing)}"
        )

    for column in required:
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise TypeError(
                f"{column} must contain numeric values"
            )


def _validate_close(close: pd.Series) -> None:
    """Validate a close-price series."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series")

    if close.empty:
        raise ValueError("close must not be empty")

    if not pd.api.types.is_numeric_dtype(close):
        raise TypeError("close must contain numeric values")


def true_range(data: pd.DataFrame) -> pd.Series:
    """Calculate True Range.

    True Range is the maximum of:
        High - Low
        |High - Previous Close|
        |Low - Previous Close|

    The first observation uses High - Low because no previous
    close exists.
    """
    _validate_ohlc(data)

    previous_close = data["close"].shift(1)

    high_low = data["high"] - data["low"]

    high_previous_close = (
        data["high"] - previous_close
    ).abs()

    low_previous_close = (
        data["low"] - previous_close
    ).abs()

    result = pd.concat(
        [
            high_low,
            high_previous_close,
            low_previous_close,
        ],
        axis=1,
    ).max(axis=1)

    return result.rename("true_range")


def atr(
    data: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range using Wilder smoothing."""
    _validate_ohlc(data)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    tr = true_range(data)

    # Wilder's smoothing is equivalent to an EMA
    # with alpha = 1 / period and adjust=False.
    result = tr.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return result.rename(f"atr_{period}")


def bollinger_bands(
    close: pd.Series,
    period: int = 20,
    standard_deviations: float = 2.0,
) -> pd.DataFrame:
    """Calculate Bollinger Bands.

    Returns:
        DataFrame containing:
            bb_middle
            bb_upper
            bb_lower
            bb_width

    Width is normalized by the middle band:
        (Upper - Lower) / Middle
    """
    _validate_close(close)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    if standard_deviations <= 0:
        raise ValueError(
            "standard_deviations must be greater than zero"
        )

    middle = close.rolling(
        window=period,
        min_periods=period,
    ).mean()

    # Pandas' rolling std uses sample standard deviation
    # by default (ddof=1), which is the conventional
    # Bollinger Band calculation.
    standard_deviation = close.rolling(
        window=period,
        min_periods=period,
    ).std()

    upper = (
        middle
        + standard_deviations * standard_deviation
    )

    lower = (
        middle
        - standard_deviations * standard_deviation
    )

    width = (
        (upper - lower)
        .div(middle)
        .replace([np.inf, -np.inf], np.nan)
    )

    return pd.DataFrame(
        {
            "bb_middle": middle,
            "bb_upper": upper,
            "bb_lower": lower,
            "bb_width": width,
        },
        index=close.index,
    )


def realized_volatility(
    close: pd.Series,
    period: int = 20,
    annualization_factor: float | None = None,
) -> pd.Series:
    """Calculate rolling realized volatility from log returns.

    The volatility is the rolling standard deviation of log returns.

    If ``annualization_factor`` is supplied, the result is annualized:
        rolling_std(log_return) * sqrt(annualization_factor)

    No annualization is applied by default because the indicator
    engine should not silently assume a particular candle timeframe.
    """
    _validate_close(close)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    if annualization_factor is not None:
        if annualization_factor <= 0:
            raise ValueError(
                "annualization_factor must be greater than zero"
            )

    if (close <= 0).any():
        raise ValueError(
            "close prices must be greater than zero"
        )

    log_returns = np.log(
        close / close.shift(1)
    )

    result = log_returns.rolling(
        window=period,
        min_periods=period,
    ).std()

    if annualization_factor is not None:
        result = result * np.sqrt(
            annualization_factor
        )

    return result.rename(
        f"realized_volatility_{period}"
    )


def add_volatility_indicators(
    data: pd.DataFrame,
    *,
    atr_period: int = 14,
    bollinger_period: int = 20,
    bollinger_std: float = 2.0,
    realized_volatility_period: int = 20,
    annualization_factor: float | None = None,
) -> pd.DataFrame:
    """Add all volatility indicators to an OHLCV DataFrame.

    Added columns:
        atr_14
        bb_middle
        bb_upper
        bb_lower
        bb_width
        realized_volatility_20
    """
    _validate_ohlc(data)

    result = data.copy()

    result[
        f"atr_{atr_period}"
    ] = atr(
        result,
        atr_period,
    )

    bands = bollinger_bands(
        result["close"],
        bollinger_period,
        bollinger_std,
    )

    result = result.join(bands)

    result[
        f"realized_volatility_{realized_volatility_period}"
    ] = realized_volatility(
        result["close"],
        realized_volatility_period,
        annualization_factor,
    )

    return result
