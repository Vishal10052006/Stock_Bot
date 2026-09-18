"""
Validation utilities for Phase 9 TrainingDataset v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.features.builder import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)


VALID_LABELS = frozenset({
    "LONG_SUCCESS",
    "SHORT_SUCCESS",
    "NO_EDGE",
})


FORBIDDEN_FUTURE_COLUMNS = frozenset({
    "outcome_timestamp",
    "outcome_bars",
    "outcome_reason",
    "target_price",
    "stop_price",
    "future_return",
    "future_close",
    "future_high",
    "future_low",
    "future_price",
})


EXPECTED_COLUMNS: tuple[str, ...] = (
    *IDENTIFIER_COLUMNS,
    *FEATURE_COLUMNS,
    "label",
)


def validate_training_dataset(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validate TrainingDataset v1.

    The dataset must contain exactly:
        timestamp
        symbol
        FeatureDataset v1 features
        label

    Future outcome metadata is forbidden.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "TrainingDataset must be a pandas DataFrame."
        )

    if data.empty:
        raise ValueError(
            "TrainingDataset must not be empty."
        )

    actual = tuple(data.columns)

    missing = [
        column
        for column in EXPECTED_COLUMNS
        if column not in data.columns
    ]

    unexpected = [
        column
        for column in data.columns
        if column not in EXPECTED_COLUMNS
    ]

    if missing or unexpected:
        messages: list[str] = []

        if missing:
            messages.append(
                f"missing columns: {missing}"
            )

        if unexpected:
            messages.append(
                f"unexpected columns: {unexpected}"
            )

        raise ValueError(
            "invalid TrainingDataset v1 schema; "
            + "; ".join(messages)
        )

    if actual != EXPECTED_COLUMNS:
        raise ValueError(
            "TrainingDataset v1 columns are in the wrong order."
        )

    timestamp = data["timestamp"]

    if not pd.api.types.is_datetime64_any_dtype(timestamp):
        raise TypeError(
            "timestamp must be a pandas datetime dtype."
        )

    if timestamp.dt.tz is None:
        raise ValueError(
            "timestamp must be timezone-aware."
        )

    if timestamp.isna().any():
        raise ValueError(
            "timestamp must not contain missing values."
        )

    if data["symbol"].isna().any():
        raise ValueError(
            "symbol must not contain missing values."
        )

    duplicates = data.duplicated(
        subset=["symbol", "timestamp"],
        keep=False,
    )

    if duplicates.any():
        raise ValueError(
            "TrainingDataset contains duplicate "
            "(symbol, timestamp) observations."
        )

    ordered = data.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    ).index

    if not data.index.equals(ordered):
        raise ValueError(
            "TrainingDataset must be chronologically ordered "
            "within each symbol."
        )

    labels = set(data["label"].dropna())

    invalid_labels = labels - VALID_LABELS

    if invalid_labels:
        raise ValueError(
            "TrainingDataset contains invalid labels: "
            f"{sorted(invalid_labels)}"
        )

    if data["label"].isna().any():
        raise ValueError(
            "TrainingDataset label must not contain missing values."
        )

    for column in FEATURE_COLUMNS:
        if column in {
            "retest_up",
            "retest_down",
            "higher_high",
            "lower_low",
            "higher_low",
            "lower_high",
        }:
            if not pd.api.types.is_bool_dtype(data[column]):
                raise TypeError(
                    f"{column} must use a boolean dtype."
                )
        else:
            if not pd.api.types.is_numeric_dtype(data[column]):
                raise TypeError(
                    f"{column} must be numeric."
                )

    numeric_columns = [
        column
        for column in FEATURE_COLUMNS
        if column not in {
            "retest_up",
            "retest_down",
            "higher_high",
            "lower_low",
            "higher_low",
            "lower_high",
        }
    ]

    finite_mask = np.isinf(
        data.loc[:, numeric_columns].to_numpy(
            dtype=float,
        )
    )

    if finite_mask.any():
        raise ValueError(
            "TrainingDataset contains infinite feature values."
        )

    forbidden = [
        column
        for column in data.columns
        if column.lower() in FORBIDDEN_FUTURE_COLUMNS
    ]

    if forbidden:
        raise ValueError(
            "TrainingDataset contains forbidden future "
            f"information: {forbidden}"
        )

    return data.copy()
