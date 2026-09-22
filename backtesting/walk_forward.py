"""AB-44 chronological walk-forward trading validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    """One chronological expanding train/test window."""

    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_rows: int
    test_rows: int


@dataclass(frozen=True, slots=True)
class WalkForwardTradingReport:
    """Immutable walk-forward trading report."""

    windows: tuple[WalkForwardWindow, ...]
    results: tuple[object, ...]


def generate_windows(
    data: pd.DataFrame,
    *,
    folds: int = 3,
    train_ratio: float = 0.60,
    test_ratio: float = 0.20,
    purge_minutes: int = 60,
) -> tuple[WalkForwardWindow, ...]:
    """Generate expanding chronological train/test windows.

    The initial training region is fixed by train_ratio.

    The remaining observations are divided into the requested number
    of chronological test blocks. Training expands after each block.

    A purge interval is inserted between the training boundary and
    the beginning of every test window.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")

    if "timestamp" not in data.columns:
        raise ValueError("data must contain a timestamp column")

    if folds < 1:
        raise ValueError("folds must be at least 1")

    if not 0 < train_ratio < 1:
        raise ValueError(
            "train_ratio must be between 0 and 1"
        )

    if not 0 < test_ratio < 1:
        raise ValueError(
            "test_ratio must be between 0 and 1"
        )

    if purge_minutes < 0:
        raise ValueError(
            "purge_minutes must not be negative"
        )

    timestamps = (
        pd.to_datetime(
            data["timestamp"],
            utc=True,
            errors="raise",
        )
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    total = len(timestamps)

    if total < folds * 3:
        raise ValueError(
            "insufficient timestamps for requested "
            "walk-forward folds"
        )

    initial_train_size = max(
        1,
        int(total * train_ratio),
    )

    remaining = total - initial_train_size

    if remaining < folds:
        raise ValueError(
            "insufficient observations for requested "
            "walk-forward folds"
        )

    # Divide the post-training region into chronological test blocks.
    base_test_size = remaining // folds
    remainder = remaining % folds

    windows: list[WalkForwardWindow] = []

    train_end_index = initial_train_size - 1

    for fold_id in range(1, folds + 1):
        # Distribute leftover observations deterministically.
        current_test_size = (
            base_test_size
            + (1 if fold_id <= remainder else 0)
        )

        test_start_index = train_end_index + 1
        test_end_index = (
            test_start_index
            + current_test_size
            - 1
        )

        if test_end_index >= total:
            raise ValueError(
                "walk-forward configuration exceeded "
                "available timestamps"
            )

        train_end = timestamps.iloc[train_end_index]

        nominal_test_start = timestamps.iloc[
            test_start_index
        ]

        test_start = (
            nominal_test_start
            + pd.Timedelta(minutes=purge_minutes)
        )

        test_end = timestamps.iloc[test_end_index]

        timestamp_series = pd.to_datetime(
            data["timestamp"],
            utc=True,
            errors="raise",
        )

        train_mask = (
            timestamp_series <= train_end
        )

        test_mask = (
            (timestamp_series > test_start)
            & (timestamp_series <= test_end)
        )

        train_rows = int(train_mask.sum())
        test_rows = int(test_mask.sum())

        if train_rows == 0:
            raise ValueError(
                f"fold {fold_id} produced an empty training set"
            )

        if test_rows == 0:
            raise ValueError(
                f"fold {fold_id} produced an empty test set "
                "after purge"
            )

        windows.append(
            WalkForwardWindow(
                fold_id=fold_id,
                train_start=timestamps.iloc[0],
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_rows=train_rows,
                test_rows=test_rows,
            )
        )

        # Expand training through the completed test block.
        train_end_index = test_end_index

    return tuple(windows)


def evaluate_walk_forward(
    data: pd.DataFrame,
    *,
    folds: int = 3,
    train_ratio: float = 0.60,
    test_ratio: float = 0.20,
    purge_minutes: int = 60,
    evaluator: Callable[
        [pd.DataFrame, pd.DataFrame],
        object,
    ],
) -> WalkForwardTradingReport:
    """Run a supplied trading evaluator on later test windows."""

    if not callable(evaluator):
        raise TypeError(
            "evaluator must be callable"
        )

    windows = generate_windows(
        data,
        folds=folds,
        train_ratio=train_ratio,
        test_ratio=test_ratio,
        purge_minutes=purge_minutes,
    )

    timestamps = pd.to_datetime(
        data["timestamp"],
        utc=True,
        errors="raise",
    )

    results: list[object] = []

    for window in windows:
        train_mask = (
            timestamps <= window.train_end
        )

        test_mask = (
            (timestamps > window.test_start)
            & (timestamps <= window.test_end)
        )

        train = data.loc[
            train_mask
        ].copy()

        test = data.loc[
            test_mask
        ].copy()

        if train.empty or test.empty:
            raise RuntimeError(
                "walk-forward window produced an empty partition"
            )

        # Explicit invariant: no future test observation may enter training.
        if train["timestamp"].max() >= test["timestamp"].min():
            raise RuntimeError(
                "walk-forward leakage detected: "
                "training reaches test period"
            )

        results.append(
            evaluator(
                train,
                test,
            )
        )

    if len(results) != len(windows):
        raise RuntimeError(
            "walk-forward evaluation did not produce "
            "one result per window"
        )

    return WalkForwardTradingReport(
        windows=windows,
        results=tuple(results),
    )
