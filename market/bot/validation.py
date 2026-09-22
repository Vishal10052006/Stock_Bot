"""Market Bot input, causality, and missing-data validation."""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def validate_ohlcv_frame(data: pd.DataFrame, required: Iterable[str] = ("timestamp", "close")) -> pd.DataFrame:
    """Validate and return a canonical UTC, timestamp-ordered copy."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    required = tuple(required)
    missing = set(required).difference(data.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    frame = data.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if frame["timestamp"].duplicated().any():
        raise ValueError("duplicate timestamps are not allowed")
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("timestamps must be monotonically increasing")
    for column in required:
        if column != "timestamp" and not pd.api.types.is_numeric_dtype(frame[column]):
            raise TypeError(f"{column} must be numeric")
    return frame


def assert_causal(output: pd.DataFrame, source: pd.DataFrame, timestamp: str = "timestamp") -> None:
    """Reject outputs containing timestamps that precede their source ordering."""
    if timestamp not in output.columns or timestamp not in source.columns:
        raise ValueError("both frames require timestamp")
    out_ts = pd.to_datetime(output[timestamp], utc=True)
    src_ts = pd.to_datetime(source[timestamp], utc=True)
    if not out_ts.is_monotonic_increasing or not src_ts.is_monotonic_increasing:
        raise ValueError("causality check requires ordered timestamps")
    if len(out_ts) and len(src_ts) and out_ts.iloc[-1] > src_ts.iloc[-1]:
        raise ValueError("output contains timestamp beyond source availability")


def finite_or_none(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    value = float(value)
    return value if np.isfinite(value) else None
