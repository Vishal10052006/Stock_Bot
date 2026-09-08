"""Causal return and volatility features for market/sector context."""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_HORIZONS: tuple[int, ...] = (1, 3, 12)


def build_context_returns(
    data: pd.DataFrame,
    *,
    price_column: str = "close",
    key_column: str | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    volatility_window: int = 20,
) -> pd.DataFrame:
    """Build causal return/volatility context from completed price bars.

    Returns are computed independently within each instrument/index series.
    No centered windows, backfilling, or future observations are used.
    """
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if data.empty:
        raise ValueError("data must not be empty")
    if "timestamp" not in data.columns:
        raise ValueError("data must contain timestamp")
    if price_column not in data.columns:
        raise ValueError(f"data must contain {price_column}")
    if not pd.api.types.is_datetime64tz_dtype(data["timestamp"]):
        raise ValueError("timestamp must be timezone-aware")
    if not pd.api.types.is_numeric_dtype(data[price_column]):
        raise TypeError(f"{price_column} must be numeric")
    if any(
        not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0
        for horizon in horizons
    ):
        raise ValueError("horizons must contain positive integers")
    if volatility_window <= 1:
        raise ValueError("volatility_window must be greater than 1")

    result = data.loc[:, [c for c in data.columns]].copy()
    result = result.sort_values(
        ([key_column] if key_column else []) + ["timestamp"]
    )

    groups = result.groupby(key_column, sort=False)[price_column] if key_column else None

    for horizon in horizons:
        name = f"return_{horizon}"
        if groups is None:
            result[name] = result[price_column].pct_change(horizon)
        else:
            result[name] = groups.pct_change(horizon)

    log_return = np.log(
        result[price_column].astype(float).where(result[price_column] > 0)
        / result[price_column].astype(float).where(result[price_column] > 0).shift(1)
    )
    if key_column is not None:
        log_return = result.groupby(key_column, sort=False)[price_column].transform(
            lambda values: np.log(values.where(values > 0) / values.where(values > 0).shift(1))
        )

    if key_column is None:
        result["volatility_20"] = log_return.rolling(volatility_window).std()
    else:
        result["volatility_20"] = log_return.groupby(
            result[key_column], sort=False
        ).transform(lambda values: values.rolling(volatility_window).std())

    return result
