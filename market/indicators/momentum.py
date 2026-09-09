"""Momentum indicators for OHLCV market data.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import pandas as pd


def _validate_close(close: pd.Series) -> None:
    """Validate the input close-price series."""
    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series")

    if close.empty:
        raise ValueError("close must not be empty")

    if not pd.api.types.is_numeric_dtype(close):
        raise TypeError("close must contain numeric values")


def rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate RSI using Wilder's smoothing method.

    Formula:
        Gain = positive close-to-close change
        Loss = negative close-to-close change

        RS  = Wilder average gain / Wilder average loss
        RSI = 100 - (100 / (1 + RS))

    The first valid RSI requires ``period`` price changes.
    """
    _validate_close(close)

    if period <= 0:
        raise ValueError("period must be greater than zero")

    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    average_gain = gain.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = loss.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = average_gain / average_loss

    result = 100.0 - (
        100.0 / (1.0 + rs)
    )

    # When there is no loss, RSI is 100.
    result = result.where(
        average_loss != 0,
        100.0,
    )

    # When both average gain and loss are zero, price is flat.
    # RSI is conventionally treated as 50.
    flat_market = (
        (average_gain == 0)
        & (average_loss == 0)
    )

    result = result.where(
        ~flat_market,
        50.0,
    )

    return result.rename(f"rsi_{period}")


def macd(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> pd.DataFrame:
    """Calculate MACD, signal line, and histogram.

    Standard configuration:
        Fast EMA  = 12
        Slow EMA  = 26
        Signal    = 9

    Returns:
        DataFrame containing:
            macd
            macd_signal
            macd_histogram
    """
    _validate_close(close)

    if fast_period <= 0:
        raise ValueError(
            "fast_period must be greater than zero"
        )

    if slow_period <= 0:
        raise ValueError(
            "slow_period must be greater than zero"
        )

    if signal_period <= 0:
        raise ValueError(
            "signal_period must be greater than zero"
        )

    if fast_period >= slow_period:
        raise ValueError(
            "fast_period must be less than slow_period"
        )

    fast_ema = close.ewm(
        span=fast_period,
        adjust=False,
        min_periods=fast_period,
    ).mean()

    slow_ema = close.ewm(
        span=slow_period,
        adjust=False,
        min_periods=slow_period,
    ).mean()

    macd_line = fast_ema - slow_ema

    signal_line = macd_line.ewm(
        span=signal_period,
        adjust=False,
        min_periods=signal_period,
    ).mean()

    histogram = macd_line - signal_line

    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
        },
        index=close.index,
    )


def roc(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Rate of Change as a percentage."""
    _validate_close(close)

    if period <= 0:
        raise ValueError("period must be greater than zero")

    result = (
        close
        .div(close.shift(period))
        .sub(1.0)
        .mul(100.0)
    )

    return result.rename(f"roc_{period}")


def add_momentum_indicators(
    data: pd.DataFrame,
    *,
    rsi_period: int = 14,
    roc_period: int = 14,
) -> pd.DataFrame:
    """Return OHLCV data with momentum indicators added.

    Added columns:
        rsi_14
        macd
        macd_signal
        macd_histogram
        roc_14
    """
    if "close" not in data.columns:
        raise ValueError(
            "missing required OHLCV columns: ['close']"
        )

    result = data.copy()

    result[f"rsi_{rsi_period}"] = rsi(
        result["close"],
        rsi_period,
    )

    macd_result = macd(result["close"])

    result = result.join(macd_result)

    result[f"roc_{roc_period}"] = roc(
        result["close"],
        roc_period,
    )

    return result
