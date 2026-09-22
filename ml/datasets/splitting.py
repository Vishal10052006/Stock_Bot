"""
Temporal train/validation/test splitting for STOCK BOT.

The splitter is designed for supervised trading data whose labels
may depend on future prices. It therefore uses chronological
boundaries and purge windows around each boundary.

No random shuffling is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from .models import TrainingDataset


@dataclass(frozen=True)
class TemporalSplitConfig:
    """
    Configuration for chronological dataset splitting.

    Ratios determine the nominal chronological boundaries.

    purge_minutes represents the maximum forward label horizon that
    must be excluded around each split boundary.
    """

    train_ratio: float = 0.70
    validation_ratio: float = 0.15
    test_ratio: float = 0.15

    purge_minutes: int = 60

    def __post_init__(self) -> None:
        """Validate split configuration."""

        ratios = (
            self.train_ratio,
            self.validation_ratio,
            self.test_ratio,
        )

        if any(ratio <= 0 for ratio in ratios):
            raise ValueError(
                "All split ratios must be greater than zero."
            )

        if abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError(
                "train_ratio + validation_ratio + test_ratio "
                "must equal 1."
            )

        if self.purge_minutes < 0:
            raise ValueError(
                "purge_minutes must not be negative."
            )


@dataclass(frozen=True)
class TemporalSplit:
    """
    Chronological train/validation/test partitions.

    The boundary metadata represents the nominal split boundaries,
    while the actual partitions exclude observations inside purge
    windows.
    """

    train: TrainingDataset
    validation: TrainingDataset
    test: TrainingDataset

    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp


def _make_dataset(
    data: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> TrainingDataset:
    """Construct a TrainingDataset from a validated subset."""

    return TrainingDataset(
        data=data.reset_index(drop=True).copy(),
        feature_columns=feature_columns,
    )


def temporal_split(
    dataset: TrainingDataset,
    config: TemporalSplitConfig | None = None,
) -> TemporalSplit:
    """
    Split a TrainingDataset chronologically with purge windows.

    The nominal boundaries are selected from global unique decision
    timestamps so every symbol observes the same temporal boundaries.

    For a boundary B and purge interval P:

        train      <= B - P
        validation > B + P

    At the second boundary:

        validation <= B2 - P
        test       > B2 + P

    This removes observations whose forward-looking labels could
    cross a partition boundary.

    No randomization or shuffling occurs.
    """

    if config is None:
        config = TemporalSplitConfig()

    if not isinstance(dataset, TrainingDataset):
        raise TypeError(
            "dataset must be a TrainingDataset."
        )

    data = dataset.data.copy()

    if data.empty:
        raise ValueError(
            "TrainingDataset must not be empty."
        )

    timestamps = (
        data["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    if len(timestamps) < 3:
        raise ValueError(
            "Temporal splitting requires at least three "
            "unique decision timestamps."
        )

    n_timestamps = len(timestamps)

    train_index = max(
        1,
        int(n_timestamps * config.train_ratio),
    )

    validation_index = max(
        train_index + 1,
        int(
            n_timestamps
            * (
                config.train_ratio
                + config.validation_ratio
            )
        ),
    )

    if validation_index >= n_timestamps:
        validation_index = n_timestamps - 1

    nominal_train_end = timestamps.iloc[
        train_index - 1
    ]

    nominal_validation_end = timestamps.iloc[
        validation_index - 1
    ]

    purge = timedelta(
        minutes=config.purge_minutes
    )

    train_end = nominal_train_end - purge
    validation_start = nominal_train_end + purge

    validation_end = nominal_validation_end - purge
    test_start = nominal_validation_end + purge

    # The purge applies on both sides of each temporal boundary.
    # Fail closed when the requested split/purge geometry leaves no
    # chronologically valid observations in one of the partitions.

    train_mask = (
        data["timestamp"] <= train_end
    )

    validation_mask = (
        (data["timestamp"] > validation_start)
        & (data["timestamp"] <= validation_end)
    )

    test_mask = (
        data["timestamp"] > test_start
    )

    train_data = data.loc[
        train_mask
    ].copy()

    validation_data = data.loc[
        validation_mask
    ].copy()

    test_data = data.loc[
        test_mask
    ].copy()

    if train_data.empty:
        raise ValueError(
            "Temporal split produced an empty training set."
        )

    if validation_data.empty:
        raise ValueError(
            "Temporal split produced an empty validation set."
        )

    if test_data.empty:
        raise ValueError(
            "Temporal split produced an empty test set."
        )

    train_data = train_data.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    )

    validation_data = validation_data.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    )

    test_data = test_data.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    )

    feature_columns = dataset.feature_columns

    return TemporalSplit(
        train=_make_dataset(
            train_data,
            feature_columns,
        ),
        validation=_make_dataset(
            validation_data,
            feature_columns,
        ),
        test=_make_dataset(
            test_data,
            feature_columns,
        ),
        train_end=train_end,
        validation_start=validation_start,
        validation_end=validation_end,
        test_start=test_start,
    )
