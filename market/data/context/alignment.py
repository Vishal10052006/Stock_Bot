"""Causal timestamp alignment for external market context."""

from __future__ import annotations

import pandas as pd


def _validate_frame(
    data: pd.DataFrame,
    name: str,
    *,
    key_column: str | None = None,
) -> None:
    if not isinstance(data, pd.DataFrame):
        raise TypeError(f"{name} must be a pandas DataFrame")
    if data.empty:
        raise ValueError(f"{name} must not be empty")
    if "timestamp" not in data.columns:
        raise ValueError(f"{name} must contain timestamp")
    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError(f"{name}.timestamp must be timezone-aware")

    if key_column is not None:
        if key_column not in data.columns:
            raise ValueError(f"{name} missing key column: {key_column}")
        if data.duplicated([key_column, "timestamp"]).any():
            raise ValueError(
                f"{name} contains duplicate key/timestamp rows"
            )

        # A keyed context may legitimately contain multiple series at the
        # same timestamp. Validate chronology independently within each key;
        # do not require one global key/timestamp ordering because the
        # downstream merge_asof operation performs its own canonical sort.
        for _, group in data.groupby(key_column, sort=False, dropna=False):
            if not group["timestamp"].is_monotonic_increasing:
                raise ValueError(
                    f"{name} timestamps must be chronological within "
                    f"each {key_column}"
                )
    else:
        if data["timestamp"].duplicated().any():
            raise ValueError(f"{name} contains duplicate timestamps")
        if not data["timestamp"].is_monotonic_increasing:
            raise ValueError(f"{name} timestamps must be chronological")


def _as_nanosecond_timestamps(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize timestamp resolution for pandas as-of joins."""
    result = data.copy()
    result["timestamp"] = result["timestamp"].dt.as_unit("ns")
    return result


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
    _validate_frame(
        observations,
        "observations",
        key_column=context_key,
    )
    _validate_frame(context, "context", key_column=context_key)

    missing = set(context_columns).difference(context.columns)
    if missing:
        raise ValueError(f"context missing columns: {sorted(missing)}")

    if context_key is not None and context_key not in observations.columns:
        raise ValueError(
            f"observations missing key column: {context_key}"
        )

    left = _as_nanosecond_timestamps(observations)
    right_columns = ["timestamp"] + list(context_columns)
    if context_key is not None:
        right_columns.append(context_key)

    right = _as_nanosecond_timestamps(
        context.loc[:, list(dict.fromkeys(right_columns))]
    )

    if context_key is None:
        right = right.sort_values("timestamp", kind="stable")
        left = left.sort_values("timestamp", kind="stable")
        merged = pd.merge_asof(
            left,
            right,
            on="timestamp",
            direction="backward",
            allow_exact_matches=True,
            suffixes=("", "_context"),
        )
    else:
        left = left.sort_values(
            ["timestamp", context_key],
            kind="stable",
        )
        right = right.sort_values(
            ["timestamp", context_key],
            kind="stable",
        )
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
