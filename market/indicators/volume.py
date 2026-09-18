"""Volume indicators for OHLCV market data.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_volume(volume: pd.Series) -> None:
    """Validate a volume series."""
    if not isinstance(volume, pd.Series):
        raise TypeError("volume must be a pandas Series")

    if volume.empty:
        raise ValueError("volume must not be empty")

    if not pd.api.types.is_numeric_dtype(volume):
        raise TypeError(
            "volume must contain numeric values"
        )

    if (volume < 0).any():
        raise ValueError(
            "volume must be non-negative"
        )


def rvol(
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Calculate Relative Volume.

    RVOL compares the current candle volume with the average
    volume of the preceding ``period`` candles.

    Formula:

        RVOL =
            Current Volume
            -----------------------------
            Mean of Previous N Volumes

    The current candle is deliberately excluded from the
    reference average to avoid using the observation being
    evaluated as part of its own baseline.
    """
    _validate_volume(volume)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    previous_average = (
        volume
        .shift(1)
        .rolling(
            window=period,
            min_periods=period,
        )
        .mean()
    )

    result = (
        volume
        .div(previous_average)
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    return result.rename(f"rvol_{period}")


def volume_change(
    volume: pd.Series,
    period: int = 1,
) -> pd.Series:
    """Calculate percentage change in volume.

    Formula:

        Volume Change =
            ((Current Volume / Previous Volume) - 1) × 100
    """
    _validate_volume(volume)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    result = (
        volume
        .div(volume.shift(period))
        .sub(1.0)
        .mul(100.0)
        .replace(
            [np.inf, -np.inf],
            np.nan,
        )
    )

    return result.rename(
        f"volume_change_{period}"
    )


def add_volume_indicators(
    data: pd.DataFrame,
    *,
    rvol_period: int = 20,
    volume_change_period: int = 1,
) -> pd.DataFrame:
    """Add volume indicators to an OHLCV DataFrame.

    Added columns:

        rvol_20
        volume_change_1
    """
    if "volume" not in data.columns:
        raise ValueError(
            "missing required OHLCV columns: ['volume']"
        )

    result = data.copy()

    result[
        f"rvol_{rvol_period}"
    ] = rvol(
        result["volume"],
        rvol_period,
    )

    result[
        f"volume_change_{volume_change_period}"
    ] = volume_change(
        result["volume"],
        volume_change_period,
    )

    return result
