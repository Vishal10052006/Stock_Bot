"""Trend indicators for OHLCV market data.

The functions in this module calculate deterministic technical indicators
from validated OHLCV data.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_ohlcv(data: pd.DataFrame) -> None:
    """Validate the minimum OHLCV columns required by this module."""
    required_columns = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing = required_columns.difference(data.columns)

    if missing:
        raise ValueError(
            f"missing required OHLCV columns: {sorted(missing)}"
        )


def ema(
    close: pd.Series,
    period: int,
) -> pd.Series:
    """Calculate exponential moving average."""
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series")

    return close.ewm(
        span=period,
        adjust=False,
        min_periods=period,
    ).mean()


def sma(
    close: pd.Series,
    period: int,
) -> pd.Series:
    """Calculate simple moving average."""
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if not isinstance(close, pd.Series):
        raise TypeError("close must be a pandas Series")

    return close.rolling(
        window=period,
        min_periods=period,
    ).mean()


def vwap(data: pd.DataFrame) -> pd.Series:
    """Calculate cumulative session VWAP.

    The input must contain:
        high, low, close, volume

    If a ``timestamp`` column is present, VWAP resets automatically at
    each calendar day. The timestamp must be timezone-aware.

    Formula:
        Typical Price = (High + Low + Close) / 3
        VWAP = cumulative(Typical Price * Volume) / cumulative(Volume)
    """
    _validate_ohlcv(data)

    if "timestamp" not in data.columns:
        raise ValueError(
            "timestamp column is required for session VWAP"
        )

    timestamps = pd.to_datetime(
        data["timestamp"],
        errors="raise",
    )

    if timestamps.dt.tz is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    typical_price = (
        data["high"]
        + data["low"]
        + data["close"]
    ) / 3.0

    price_volume = typical_price * data["volume"]

    session_key = timestamps.dt.date

    cumulative_pv = price_volume.groupby(
        session_key,
        sort=False,
    ).cumsum()

    cumulative_volume = data["volume"].groupby(
        session_key,
        sort=False,
    ).cumsum()

    result = cumulative_pv / cumulative_volume

    # A zero-volume session cannot produce a meaningful VWAP.
    result = result.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    return result.rename("vwap")


def add_trend_indicators(
    data: pd.DataFrame,
    *,
    sma_period: int = 20,
) -> pd.DataFrame:
    """Return a copy of OHLCV data with trend indicators added.

    Added columns:
        ema_9
        ema_20
        ema_50
        sma
        vwap
    """
    _validate_ohlcv(data)

    if sma_period <= 0:
        raise ValueError(
            "sma_period must be greater than zero"
        )

    result = data.copy()

    result["ema_9"] = ema(
        result["close"],
        9,
    )

    result["ema_20"] = ema(
        result["close"],
        20,
    )

    result["ema_50"] = ema(
        result["close"],
        50,
    )

    result["sma"] = sma(
        result["close"],
        sma_period,
    )

    result["vwap"] = vwap(result)

    return result
