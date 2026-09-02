"""Price-structure indicators for OHLCV market data.

The calculations in this module are causal: current structure values
use only the current candle and previously completed candles.

Reference:
    ROADMAP_STOCK-BOT.pdf — Phase 4, Indicator Engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _validate_ohlc(data: pd.DataFrame) -> None:
    """Validate the OHLC columns required by structure indicators."""
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


def support_resistance(
    data: pd.DataFrame,
    period: int = 20,
) -> pd.DataFrame:
    """Calculate causal rolling support and resistance.

    Support is the lowest low among the preceding ``period`` candles.

    Resistance is the highest high among the preceding ``period`` candles.

    The current candle is deliberately excluded from both calculations.
    This makes the values suitable for live decision-making and prevents
    the current candle from defining its own reference level.
    """
    _validate_ohlc(data)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    previous_lows = (
        data["low"]
        .shift(1)
        .rolling(
            window=period,
            min_periods=period,
        )
        .min()
    )

    previous_highs = (
        data["high"]
        .shift(1)
        .rolling(
            window=period,
            min_periods=period,
        )
        .max()
    )

    return pd.DataFrame(
        {
            f"support_{period}": previous_lows,
            f"resistance_{period}": previous_highs,
        },
        index=data.index,
    )


def structure_flags(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate basic causal price-structure flags.

    Flags compare the current candle with immediately preceding
    price information.

    Returns:
        higher_high:
            Current high is greater than the previous high.

        lower_low:
            Current low is lower than the previous low.

        higher_low:
            Current low is greater than the previous low.

        lower_high:
            Current high is lower than the previous high.
    """
    _validate_ohlc(data)

    previous_high = data["high"].shift(1)
    previous_low = data["low"].shift(1)

    # Comparisons involving the first candle have no valid
    # previous-candle reference. Use pandas nullable booleans
    # so the unavailable state is represented as <NA> rather
    # than incorrectly becoming False.
    higher_high = (
        data["high"] > previous_high
    ).astype("boolean")

    lower_low = (
        data["low"] < previous_low
    ).astype("boolean")

    higher_low = (
        data["low"] > previous_low
    ).astype("boolean")

    lower_high = (
        data["high"] < previous_high
    ).astype("boolean")

    # Explicitly mark the first observation as unavailable.
    higher_high.iloc[0] = pd.NA
    lower_low.iloc[0] = pd.NA
    higher_low.iloc[0] = pd.NA
    lower_high.iloc[0] = pd.NA

    return pd.DataFrame(
        {
            "higher_high": higher_high,
            "lower_low": lower_low,
            "higher_low": higher_low,
            "lower_high": lower_high,
        },
        index=data.index,
    )


def structure_distances(
    data: pd.DataFrame,
    period: int = 20,
) -> pd.DataFrame:
    """Calculate percentage distance from support and resistance.

    Formulas:

        Distance to Support =
            ((Close - Support) / Support) × 100

        Distance to Resistance =
            ((Resistance - Close) / Resistance) × 100

    Positive values indicate the close is between the two levels.
    """
    _validate_ohlc(data)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    levels = support_resistance(
        data,
        period,
    )

    support_column = f"support_{period}"
    resistance_column = f"resistance_{period}"

    support = levels[support_column]
    resistance = levels[resistance_column]

    distance_to_support = (
        (data["close"] - support)
        .div(support)
        .mul(100.0)
    )

    distance_to_resistance = (
        (resistance - data["close"])
        .div(resistance)
        .mul(100.0)
    )

    return pd.DataFrame(
        {
            "distance_to_support_pct": (
                distance_to_support
            ),
            "distance_to_resistance_pct": (
                distance_to_resistance
            ),
        },
        index=data.index,
    )


def add_structure_indicators(
    data: pd.DataFrame,
    *,
    period: int = 20,
) -> pd.DataFrame:
    """Add price-structure indicators to an OHLCV DataFrame.

    Added columns:

        support_20
        resistance_20
        distance_to_support_pct
        distance_to_resistance_pct
        higher_high
        lower_low
        higher_low
        lower_high
    """
    _validate_ohlc(data)

    result = data.copy()

    levels = support_resistance(
        result,
        period,
    )

    distances = structure_distances(
        result,
        period,
    )

    flags = structure_flags(result)

    result = result.join(levels)
    result = result.join(distances)
    result = result.join(flags)

    return result
