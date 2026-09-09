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


def previous_day_levels(
    data: pd.DataFrame,
    *,
    timestamp_column: str = "timestamp",
    timezone: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Calculate the previous completed trading day's high and low.

    The current trading day's candles never contribute to its own
    previous-day levels. The calculation first aggregates each
    session independently and then shifts the completed session
    values forward by one trading date.

    If a ``symbol`` column exists, levels are calculated independently
    for each symbol. This prevents one instrument from contaminating
    another instrument's levels.

    Args:
        data:
            OHLCV DataFrame containing high, low and a timezone-aware
            timestamp column.

        timestamp_column:
            Name of the timestamp column.

        timezone:
            Exchange/session timezone used to determine the trading day.

    Returns:
        DataFrame containing:

            previous_day_high
            previous_day_low
    """
    _validate_ohlc(data)

    if timestamp_column not in data.columns:
        raise ValueError(
            f"missing required timestamp column: "
            f"{timestamp_column}"
        )

    timestamps = pd.to_datetime(
        data[timestamp_column],
        errors="raise",
    )

    if timestamps.dt.tz is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    session_dates = timestamps.dt.tz_convert(
        timezone
    ).dt.normalize()

    working = pd.DataFrame(
        {
            "_session_date": session_dates,
            "_high": data["high"].to_numpy(),
            "_low": data["low"].to_numpy(),
        },
        index=data.index,
    )

    group_columns = ["_session_date"]

    if "symbol" in data.columns:
        working["_symbol"] = (
            data["symbol"].astype(str).str.upper()
        )
        group_columns = [
            "_symbol",
            "_session_date",
        ]

    daily = (
        working
        .groupby(
            group_columns,
            sort=True,
            observed=True,
        )
        .agg(
            _day_high=("_high", "max"),
            _day_low=("_low", "min"),
        )
    )

    if "symbol" in data.columns:
        daily["previous_day_high"] = (
            daily.groupby(
                level="_symbol",
                sort=False,
            )["_day_high"].shift(1)
        )

        daily["previous_day_low"] = (
            daily.groupby(
                level="_symbol",
                sort=False,
            )["_day_low"].shift(1)
        )
    else:
        daily["previous_day_high"] = (
            daily["_day_high"].shift(1)
        )

        daily["previous_day_low"] = (
            daily["_day_low"].shift(1)
        )

    lookup_columns = [
        "previous_day_high",
        "previous_day_low",
    ]

    if "symbol" in data.columns:
        keys = pd.MultiIndex.from_arrays(
            [
                data["symbol"].astype(str).str.upper(),
                session_dates,
            ],
            names=[
                "_symbol",
                "_session_date",
            ],
        )
    else:
        keys = pd.Index(
            session_dates,
            name="_session_date",
        )

    result = daily[lookup_columns].reindex(keys)
    result.index = data.index

    return result


def opening_range(
    data: pd.DataFrame,
    *,
    timestamp_column: str = "timestamp",
    timezone: str = "Asia/Kolkata",
    session_start: str = "09:15",
    opening_minutes: int = 15,
) -> pd.DataFrame:
    """Calculate the completed opening-range high and low.

    The opening range contains candles beginning at the configured
    session start and ending immediately before the opening-range
    completion time.

    For the default NSE configuration:

        09:15, 09:20, 09:25 -> opening range
        09:30 onward        -> levels become available

    The current candle is never used to define the opening range before
    the opening window has completed.

    If a ``symbol`` column exists, calculations are isolated per symbol.

    Args:
        data:
            OHLCV DataFrame with timezone-aware timestamps.

        timestamp_column:
            Column containing candle timestamps.

        timezone:
            Exchange/session timezone.

        session_start:
            Local session opening time in HH:MM format.

        opening_minutes:
            Length of the opening range in minutes.

    Returns:
        DataFrame containing:

            opening_range_high
            opening_range_low
            opening_range_width
    """
    _validate_ohlc(data)

    if timestamp_column not in data.columns:
        raise ValueError(
            f"missing required timestamp column: "
            f"{timestamp_column}"
        )

    if opening_minutes <= 0:
        raise ValueError(
            "opening_minutes must be greater than zero"
        )

    try:
        start_hour, start_minute = (
            int(value)
            for value in session_start.split(":")
        )
    except (AttributeError, ValueError):
        raise ValueError(
            "session_start must use HH:MM format"
        ) from None

    if not (
        0 <= start_hour <= 23
        and 0 <= start_minute <= 59
    ):
        raise ValueError(
            "session_start must use HH:MM format"
        )

    timestamps = pd.to_datetime(
        data[timestamp_column],
        errors="raise",
    )

    if timestamps.dt.tz is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    local_timestamps = timestamps.dt.tz_convert(
        timezone
    )

    session_dates = local_timestamps.dt.normalize()

    start_offset = pd.Timedelta(
        hours=start_hour,
        minutes=start_minute,
    )

    opening_start = (
        session_dates + start_offset
    )

    opening_end = (
        opening_start
        + pd.Timedelta(minutes=opening_minutes)
    )

    # Only candles whose start timestamp falls inside the opening
    # interval contribute to the opening range.
    in_opening_range = (
        (local_timestamps >= opening_start)
        & (local_timestamps < opening_end)
    )

    working = pd.DataFrame(
        {
            "_session_date": session_dates,
            "_opening": in_opening_range,
            "_high": data["high"].to_numpy(),
            "_low": data["low"].to_numpy(),
        },
        index=data.index,
    )

    group_columns = ["_session_date"]

    if "symbol" in data.columns:
        working["_symbol"] = (
            data["symbol"].astype(str).str.upper()
        )
        group_columns = [
            "_symbol",
            "_session_date",
        ]

    opening_data = working.loc[
        working["_opening"]
    ]

    if opening_data.empty:
        return pd.DataFrame(
            {
                "opening_range_high": np.nan,
                "opening_range_low": np.nan,
                "opening_range_width": np.nan,
            },
            index=data.index,
        )

    ranges = (
        opening_data
        .groupby(
            group_columns,
            sort=True,
            observed=True,
        )
        .agg(
            _opening_range_high=("_high", "max"),
            _opening_range_low=("_low", "min"),
        )
    )

    ranges["opening_range_width"] = (
        ranges["_opening_range_high"]
        - ranges["_opening_range_low"]
    )

    if "symbol" in data.columns:
        keys = pd.MultiIndex.from_arrays(
            [
                data["symbol"].astype(str).str.upper(),
                session_dates,
            ],
            names=[
                "_symbol",
                "_session_date",
            ],
        )
    else:
        keys = pd.Index(
            session_dates,
            name="_session_date",
        )

    levels = ranges[
        [
            "_opening_range_high",
            "_opening_range_low",
            "opening_range_width",
        ]
    ].reindex(keys)

    levels.index = data.index

    # Do not expose the final opening range until the opening window
    # has completely elapsed. This prevents look-ahead leakage.
    complete = local_timestamps >= opening_end

    levels.loc[~complete, :] = np.nan

    return levels.rename(
        columns={
            "_opening_range_high": "opening_range_high",
            "_opening_range_low": "opening_range_low",
        }
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


def swing_levels(
    data: pd.DataFrame,
    *,
    left_bars: int = 2,
    right_bars: int = 2,
) -> pd.DataFrame:
    """Calculate causally confirmed swing-high and swing-low levels.

    A pivot candle is considered a swing high when its high is greater
    than the highs of the configured number of candles on both sides.

    A pivot candle is considered a swing low when its low is lower than
    the lows of the configured number of candles on both sides.

    The pivot is only exposed after the right-side confirmation candles
    have completed. The returned values are therefore the latest
    confirmed swing levels available at each row.

    If a ``symbol`` column exists, each symbol is processed independently.

    Args:
        data:
            OHLCV DataFrame.

        left_bars:
            Number of candles required to the left of a pivot.

        right_bars:
            Number of candles required to the right for confirmation.

    Returns:
        DataFrame containing:

            swing_high
            swing_low
    """
    _validate_ohlc(data)

    if left_bars <= 0:
        raise ValueError(
            "left_bars must be greater than zero"
        )

    if right_bars <= 0:
        raise ValueError(
            "right_bars must be greater than zero"
        )

    result = pd.DataFrame(
        {
            "swing_high": np.nan,
            "swing_low": np.nan,
        },
        index=data.index,
    )

    def process_group(group: pd.DataFrame) -> pd.DataFrame:
        """Process one symbol while preserving causal confirmation."""
        highs = group["high"].to_numpy(dtype=float)
        lows = group["low"].to_numpy(dtype=float)

        swing_high = np.full(
            len(group),
            np.nan,
            dtype=float,
        )

        swing_low = np.full(
            len(group),
            np.nan,
            dtype=float,
        )

        latest_high = np.nan
        latest_low = np.nan

        # The pivot is right_bars behind the current confirmation row.
        for confirmation_index in range(
            len(group)
        ):
            pivot_index = (
                confirmation_index - right_bars
            )

            if pivot_index >= left_bars:
                left_start = (
                    pivot_index - left_bars
                )
                left_end = pivot_index

                right_start = (
                    pivot_index + 1
                )
                right_end = (
                    pivot_index + right_bars + 1
                )

                pivot_high = highs[pivot_index]
                pivot_low = lows[pivot_index]

                left_highs = highs[
                    left_start:left_end
                ]
                right_highs = highs[
                    right_start:right_end
                ]

                left_lows = lows[
                    left_start:left_end
                ]
                right_lows = lows[
                    right_start:right_end
                ]

                if (
                    pivot_high > left_highs.max()
                    and pivot_high > right_highs.max()
                ):
                    latest_high = pivot_high

                if (
                    pivot_low < left_lows.min()
                    and pivot_low < right_lows.min()
                ):
                    latest_low = pivot_low

            swing_high[confirmation_index] = latest_high
            swing_low[confirmation_index] = latest_low

        return pd.DataFrame(
            {
                "swing_high": swing_high,
                "swing_low": swing_low,
            },
            index=group.index,
        )

    if "symbol" in data.columns:
        for _, group in data.groupby(
            data["symbol"].astype(str).str.upper(),
            sort=False,
            observed=True,
        ):
            result.loc[group.index] = process_group(
                group
            ).to_numpy()
    else:
        result = process_group(data)

    return result


def breakouts(
    data: pd.DataFrame,
    *,
    period: int = 20,
) -> pd.DataFrame:
    """Calculate causal breakout and breakdown flags.

    A breakout-up occurs when the current close is strictly above
    the highest high from the preceding ``period`` candles.

    A breakout-down occurs when the current close is strictly below
    the lowest low from the preceding ``period`` candles.

    The current candle is excluded from the reference levels so that
    it cannot define the level it is simultaneously breaking.

    Returns:
        DataFrame containing:

            breakout_up
            breakout_down
            breakout_distance_pct

    ``breakout_distance_pct`` is positive for an upward breakout and
    negative for a downward breakout. It is zero when no breakout is
    detected.
    """
    _validate_ohlc(data)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    # Shift first so the current candle cannot define its own
    # breakout reference level.
    previous_high = (
        data["high"]
        .shift(1)
        .rolling(
            window=period,
            min_periods=period,
        )
        .max()
    )

    previous_low = (
        data["low"]
        .shift(1)
        .rolling(
            window=period,
            min_periods=period,
        )
        .min()
    )

    breakout_up = (
        data["close"] > previous_high
    ).astype("boolean")

    breakout_down = (
        data["close"] < previous_low
    ).astype("boolean")

    # The first period observations have no valid reference level.
    unavailable = (
        previous_high.isna()
        | previous_low.isna()
    )

    breakout_up.loc[unavailable] = pd.NA
    breakout_down.loc[unavailable] = pd.NA

    distance_up = (
        (data["close"] - previous_high)
        .div(previous_high)
        .mul(100.0)
    )

    distance_down = (
        (data["close"] - previous_low)
        .div(previous_low)
        .mul(100.0)
    )

    distance = pd.Series(
        np.nan,
        index=data.index,
        dtype=float,
    )

    distance.loc[breakout_up == True] = (
        distance_up.loc[breakout_up == True]
    )

    distance.loc[breakout_down == True] = (
        -distance_down.loc[breakout_down == True]
    )

    return pd.DataFrame(
        {
            "breakout_up": breakout_up,
            "breakout_down": breakout_down,
            "breakout_distance_pct": distance,
        },
        index=data.index,
    )




def vwap_distance(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate percentage distance of close from session VWAP.

    Formula:

        VWAP distance =
            ((Close - VWAP) / VWAP) × 100

    Positive values mean price is above VWAP.
    Negative values mean price is below VWAP.

    The existing session-aware VWAP implementation from ``trend.py`` is
    reused so VWAP session boundaries remain consistent across the system.
    """
    _validate_ohlc(data)

    required = {"volume", "timestamp"}
    missing = required.difference(data.columns)

    if missing:
        raise ValueError(
            f"missing required columns: {sorted(missing)}"
        )

    if not pd.api.types.is_numeric_dtype(data["volume"]):
        raise TypeError(
            "volume must contain numeric values"
        )

    # Import locally to keep the structure module independent from the
    # trend module at import time.
    from market.indicators.trend import vwap

    session_vwap = vwap(data)

    distance = (
        (data["close"] - session_vwap)
        .div(session_vwap)
        .mul(100.0)
    )

    return pd.DataFrame(
        {
            "vwap_distance_pct": distance,
        },
        index=data.index,
    )

def retests(
    data: pd.DataFrame,
    *,
    period: int = 20,
) -> pd.DataFrame:
    """Detect causal retests of previously broken structure levels.

    A bullish retest occurs when:
        1. A previous candle closed above its preceding resistance.
        2. That broken resistance becomes the active bullish level.
        3. A later candle touches or crosses that level with its low.
        4. The later candle closes back above the level.

    A bearish retest is the symmetric case for broken support.

    The breakout candle itself cannot be classified as a retest because
    the broken level must already exist before the retest is evaluated.

    The calculation is performed independently for each symbol when a
    ``symbol`` column is present.

    Returns:
        DataFrame containing:

            retest_up
            retest_down
            retest_level
            retest_distance_pct

    ``retest_distance_pct`` is positive for a bullish retest and negative
    for a bearish retest. It is zero when no retest is detected.
    """
    _validate_ohlc(data)

    if period <= 0:
        raise ValueError(
            "period must be greater than zero"
        )

    result = pd.DataFrame(
        {
            "retest_up": pd.Series(
                pd.NA,
                index=data.index,
                dtype="boolean",
            ),
            "retest_down": pd.Series(
                pd.NA,
                index=data.index,
                dtype="boolean",
            ),
            "retest_level": np.nan,
            "retest_distance_pct": np.nan,
        },
        index=data.index,
    )

    def process_group(group: pd.DataFrame) -> pd.DataFrame:
        """Process one symbol without allowing cross-symbol state."""
        highs = group["high"].to_numpy(dtype=float)
        lows = group["low"].to_numpy(dtype=float)
        closes = group["close"].to_numpy(dtype=float)

        previous_high = (
            group["high"]
            .shift(1)
            .rolling(
                window=period,
                min_periods=period,
            )
            .max()
            .to_numpy(dtype=float)
        )

        previous_low = (
            group["low"]
            .shift(1)
            .rolling(
                window=period,
                min_periods=period,
            )
            .min()
            .to_numpy(dtype=float)
        )

        retest_up = pd.Series(
            pd.NA,
            index=group.index,
            dtype="boolean",
        )
        retest_down = pd.Series(
            pd.NA,
            index=group.index,
            dtype="boolean",
        )

        levels = np.full(
            len(group),
            np.nan,
            dtype=float,
        )

        distances = np.full(
            len(group),
            np.nan,
            dtype=float,
        )

        active_level = np.nan
        active_direction = 0

        for index in range(len(group)):
            # A complete reference window is required before a breakout
            # can establish a retest level.
            if (
                not np.isnan(previous_high[index])
                and not np.isnan(previous_low[index])
            ):
                # Once the reference window is complete, the retest
                # state is determinable for this candle. Default to
                # False and promote it to True only when a valid
                # retest is detected below.
                retest_up.iloc[index] = False
                retest_down.iloc[index] = False

                close = closes[index]

                breakout_up = (
                    close > previous_high[index]
                )
                breakout_down = (
                    close < previous_low[index]
                )

                # First check whether this candle retests a level that
                # was established by an earlier breakout.
                if (
                    active_direction == 1
                    and not np.isnan(active_level)
                ):
                    touched = lows[index] <= active_level

                    if touched and close > active_level:
                        retest_up.iloc[index] = True
                        levels[index] = active_level
                        distances[index] = (
                            (close - active_level)
                            / active_level
                            * 100.0
                        )

                elif (
                    active_direction == -1
                    and not np.isnan(active_level)
                ):
                    touched = highs[index] >= active_level

                    if touched and close < active_level:
                        retest_down.iloc[index] = True
                        levels[index] = active_level
                        distances[index] = (
                            -(
                                (active_level - close)
                                / active_level
                                * 100.0
                            )
                        )

                # A new breakout establishes the level for a future
                # candle. It is deliberately processed after retest
                # detection so the breakout candle cannot retest itself.
                if breakout_up:
                    active_level = previous_high[index]
                    active_direction = 1

                elif breakout_down:
                    active_level = previous_low[index]
                    active_direction = -1

        return pd.DataFrame(
            {
                "retest_up": retest_up,
                "retest_down": retest_down,
                "retest_level": levels,
                "retest_distance_pct": distances,
            },
            index=group.index,
        )

    if "symbol" in data.columns:
        for _, group in data.groupby(
            data["symbol"].astype(str).str.upper(),
            sort=False,
            observed=True,
        ):
            result.loc[group.index] = process_group(
                group
            ).to_numpy()
    else:
        result = process_group(data)

    return result

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
        swing_high
        swing_low
        previous_day_high
        previous_day_low
        opening_range_high
        opening_range_low
        opening_range_width
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

    swings = swing_levels(
        result,
    )

    result = result.join(swings)

    retest_values = retests(
        result,
        period=period,
    )

    result = result.join(retest_values)

    # Session-aware indicators require timestamps. Preserve the
    # existing OHLC-only structure API for callers without timestamps.
    if "timestamp" in result.columns:
        previous_day = previous_day_levels(
            result,
        )

        opening = opening_range(
            result,
        )

        result = result.join(previous_day)
        result = result.join(opening)

        vwap_values = vwap_distance(result)
        result = result.join(vwap_values)

    return result
