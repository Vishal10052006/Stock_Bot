"""Causal timestamp alignment for external market context."""

from __future__ import annotations

import pandas as pd


def _validate_frame(data: pd.DataFrame, name: str) -> None:
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    if data.empty:
        raise ValueError(f"{name} must not be empty")
    if "timestamp" not in data.columns:
        raise ValueError(f"{name} must contain timestamp")
    if not pd.api.types.is_datetime64tz_dtype(data["timestamp"]):
        raise ValueError(f"{name}.timestamp must be timezone-aware")
    if data["timestamp"].duplicated().any():
        raise ValueError(f"{name} contains duplicate timestamps")
    if not data["timestamp"].is_monotonic_increasing:
        raise ValueError(f"{name} timestamps must be chronological")


def align_context(
    observations: pd.DataFrame,
    context: pd.DataFrame,
    *,
    context_columns: tuple[str, ...],
    context_key: str | None = None,
) -> pd.DataFrame:
    """Backward/as-of join context to observations without future leakage.

    The context row selected for an observation always satisfies
    ``context.timestamp <= observation.timestamp``. Exact timestamp matches
    are allowed because canonical bars represent the same completed interval.
    """
    _validate_frame(observations, "observations")
    _validate_frame(context, "context")

    missing = set(context_columns).difference(context.columns)
    if missing:
        raise ValueError(f"context missing columns: {sorted(missing)}")

    if context_key is not None and context_key not in context.columns:
        raise ValueError(f"context missing key column: {context_key}")

    left = observations.copy()
    right_columns = ["timestamp"] + list(context_columns)
    if context_key is not None:
        right_columns.append(context_key)

    right = context.loc[:, list(dict.fromkeys(right_columns))].copy()

    if context_key is None:
        right = right.sort_values("timestamp")
        left = left.sort_values("timestamp")
        merged = pd.merge_asof(
            left,
            right,
            on="timestamp",
            direction="backward",
            allow_exact_matches=True,
            suffixes=("", "_context"),
        )
    else:
        if context_key not in left.columns:
            raise ValueError(f"observations missing key column: {context_key}")
        if right.duplicated([context_key, "timestamp"]).any():
            raise ValueError("context contains duplicate key/timestamp rows")
        left = left.sort_values(["timestamp", context_key])
        right = right.sort_values(["timestamp", context_key])
        merged = pd.merge_asof(
            left,
            right,
            on="timestamp",
            by=context_key,
            direction="backward",
            allow_exact_matches=True,
            suffixes=("", "_context"),
        )

    return merged.sort_index()
