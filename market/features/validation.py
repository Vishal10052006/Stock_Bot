"""Validation utilities for STOCK BOT FeatureDataset v1.

Phase 5 validation rules:
    - Enforce the frozen FeatureDataset v1 schema.
    - Require timestamp and symbol identifiers.
    - Reject duplicate observations.
    - Require timezone-aware timestamps.
    - Require chronological ordering within each symbol.
    - Reject infinite numeric values.
    - Preserve legitimate NaN warm-up/unavailability values.
    - Reject target/label columns from the feature dataset.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 5, Feature Engineering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market.features.builder import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)


# ---------------------------------------------------------------------------
# Public validation contract
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS: tuple[str, ...] = (
    *IDENTIFIER_COLUMNS,
    *FEATURE_COLUMNS,
)

BOOLEAN_FEATURES: frozenset[str] = frozenset({
    "retest_up",
    "retest_down",
    "higher_high",
    "lower_low",
    "higher_low",
    "lower_high",
})

NUMERIC_FEATURES: tuple[str, ...] = tuple(
    column
    for column in FEATURE_COLUMNS
    if column not in BOOLEAN_FEATURES
)

FORBIDDEN_TARGET_COLUMNS: frozenset[str] = frozenset({
    "target",
    "label",
    "y",
    "target_return",
    "future_return",
    "future_close",
    "future_high",
    "future_low",
    "future_price",
    "entry_signal",
    "exit_signal",
})


def _validate_dataframe(data: pd.DataFrame) -> None:
    """Validate the input object and basic schema."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError(
            "FeatureDataset must be a pandas DataFrame"
        )

    if data.empty:
        raise ValueError(
            "FeatureDataset must not be empty"
        )


def validate_schema(data: pd.DataFrame) -> None:
    """Validate the exact FeatureDataset v1 column schema."""
    _validate_dataframe(data)

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
        messages = []

        if missing:
            messages.append(
                f"missing columns: {missing}"
            )

        if unexpected:
            messages.append(
                f"unexpected columns: {unexpected}"
            )

        raise ValueError(
            "invalid FeatureDataset v1 schema; "
            + "; ".join(messages)
        )

    if actual != EXPECTED_COLUMNS:
        raise ValueError(
            "FeatureDataset v1 columns are in the wrong order"
        )


def validate_identifiers(data: pd.DataFrame) -> None:
    """Validate timestamp and symbol identifiers."""
    timestamp = data["timestamp"]
    symbol = data["symbol"]

    if not pd.api.types.is_datetime64_any_dtype(timestamp):
        raise TypeError(
            "timestamp must be a pandas datetime dtype"
        )

    if timestamp.dt.tz is None:
        raise ValueError(
            "timestamp must be timezone-aware"
        )

    if symbol.isna().any():
        raise ValueError(
            "symbol must not contain missing values"
        )

    if timestamp.isna().any():
        raise ValueError(
            "timestamp must not contain missing values"
        )


def validate_duplicates(data: pd.DataFrame) -> None:
    """Reject duplicate timestamp/symbol observations."""
    duplicates = data.duplicated(
        subset=["symbol", "timestamp"],
        keep=False,
    )

    if duplicates.any():
        duplicate_rows = data.loc[
            duplicates,
            ["symbol", "timestamp"],
        ]

        raise ValueError(
            "duplicate FeatureDataset observations found: "
            f"{duplicate_rows.to_dict('records')}"
        )


def validate_order(data: pd.DataFrame) -> None:
    """Require chronological order within each symbol."""
    ordered = data.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    ).index

    if not data.index.equals(ordered):
        raise ValueError(
            "FeatureDataset must be chronologically ordered "
            "within each symbol"
        )


def validate_dtypes(data: pd.DataFrame) -> None:
    """Validate numeric and nullable boolean feature dtypes."""
    for column in NUMERIC_FEATURES:
        if not pd.api.types.is_numeric_dtype(data[column]):
            raise TypeError(
                f"{column} must be numeric"
            )

    for column in BOOLEAN_FEATURES:
        if not pd.api.types.is_bool_dtype(data[column]):
            raise TypeError(
                f"{column} must use a boolean dtype"
            )


def validate_finite_values(data: pd.DataFrame) -> None:
    """Reject positive and negative infinity in numeric features."""
    numeric = data.loc[:, NUMERIC_FEATURES]

    infinite_mask = np.isinf(
        numeric.to_numpy(dtype=float)
    )

    if infinite_mask.any():
        rows, columns = np.where(infinite_mask)

        locations = [
            (
                int(row),
                NUMERIC_FEATURES[int(column)],
            )
            for row, column in zip(rows, columns)
        ]

        raise ValueError(
            "FeatureDataset contains infinite numeric values: "
            f"{locations}"
        )


def validate_target_contamination(data: pd.DataFrame) -> None:
    """Reject columns that belong to target/label generation."""
    contaminated = [
        column
        for column in data.columns
        if column.lower() in FORBIDDEN_TARGET_COLUMNS
    ]

    if contaminated:
        raise ValueError(
            "FeatureDataset contains target/label columns: "
            f"{contaminated}"
        )


def validate_feature_dataset(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Validate and return FeatureDataset v1.

    Validation does not mutate the input DataFrame.

    NaN values are allowed because indicator warm-up periods and
    causally unavailable features legitimately produce missing values.
    """
    validate_schema(data)
    validate_identifiers(data)
    validate_duplicates(data)
    validate_order(data)
    validate_dtypes(data)
    validate_finite_values(data)
    validate_target_contamination(data)

    return data.copy()


class FeatureDatasetValidator:
    """Object-oriented wrapper around FeatureDataset v1 validation."""

    def validate(
        self,
        data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Validate and return a copy of the FeatureDataset."""
        return validate_feature_dataset(data)
