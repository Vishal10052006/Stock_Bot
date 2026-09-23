"""AB-44 chronological, purged walk-forward validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from utils.fingerprint import artifact_fingerprint


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
    purged_rows: int


@dataclass(frozen=True, slots=True)
class WalkForwardTradingReport:
    """Immutable walk-forward trading report."""

    windows: tuple[WalkForwardWindow, ...]
    results: tuple[object, ...]

    @property
    def fingerprint(self) -> str:
        """Return a deterministic identity for the complete WF artifact."""
        return artifact_fingerprint(
            {
                "artifact_type": "WalkForwardTradingReport",
                "windows": self.windows,
                "results": self.results,
            }
        )


def generate_windows(
    data: pd.DataFrame,
    *,
    folds: int = 3,
    train_ratio: float = 0.60,
    test_ratio: float = 0.20,
    purge_minutes: int = 60,
) -> tuple[WalkForwardWindow, ...]:
    """Generate deterministic expanding chronological train/test windows.

    test_ratio is retained for public compatibility. The post-training region
    is divided evenly across folds so each observation belongs to at most one
    test block. Purging removes the configured interval before each test block.
    """

    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if "timestamp" not in data.columns:
        raise ValueError("data must contain a timestamp column")
    if folds < 1:
        raise ValueError("folds must be at least 1")
    if not 0 < train_ratio < 1:
        raise ValueError("train_ratio must be between 0 and 1")
    if not 0 < test_ratio < 1:
        raise ValueError("test_ratio must be between 0 and 1")
    if purge_minutes < 0:
        raise ValueError("purge_minutes must not be negative")

    timestamps = (
        pd.to_datetime(data["timestamp"], utc=True, errors="raise")
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )
    total = len(timestamps)

    if total < folds * 3:
        raise ValueError(
            "insufficient timestamps for requested walk-forward folds"
        )

    initial_train_size = max(1, int(total * train_ratio))
    remaining = total - initial_train_size
    if remaining < folds:
        raise ValueError(
            "insufficient observations for requested walk-forward folds"
        )

    base_test_size, remainder = divmod(remaining, folds)
    windows: list[WalkForwardWindow] = []
    train_end_index = initial_train_size - 1

    timestamp_series = pd.to_datetime(
        data["timestamp"], utc=True, errors="raise"
    )

    for fold_id in range(1, folds + 1):
        current_test_size = base_test_size + (
            1 if fold_id <= remainder else 0
        )
        test_start_index = train_end_index + 1
        test_end_index = test_start_index + current_test_size - 1

        if test_end_index >= total:
            raise ValueError(
                "walk-forward configuration exceeded available timestamps"
            )

        train_end = timestamps.iloc[train_end_index]
        nominal_test_start = timestamps.iloc[test_start_index]
        purged_test_boundary = (
            nominal_test_start + pd.Timedelta(minutes=purge_minutes)
        )
        test_mask = (
            (timestamp_series > purged_test_boundary)
            & (timestamp_series <= timestamps.iloc[test_end_index])
        )
        train_mask = timestamp_series <= train_end

        train_rows = int(train_mask.sum())
        test_rows = int(test_mask.sum())

        if train_rows == 0:
            raise ValueError(f"fold {fold_id} produced an empty training set")
        if test_rows == 0:
            raise ValueError(
                f"fold {fold_id} produced an empty test set after purge"
            )

        actual_test_start = timestamp_series.loc[test_mask].min()
        test_end = timestamps.iloc[test_end_index]
        purged_rows = int(
            (
                (timestamp_series > train_end)
                & (timestamp_series < actual_test_start)
            ).sum()
        )

        windows.append(
            WalkForwardWindow(
                fold_id=fold_id,
                train_start=timestamps.iloc[0],
                train_end=train_end,
                test_start=actual_test_start,
                test_end=test_end,
                train_rows=train_rows,
                test_rows=test_rows,
                purged_rows=purged_rows,
            )
        )
        train_end_index = test_end_index

    return tuple(windows)


def evaluate_walk_forward(
    data: pd.DataFrame,
    *,
    folds: int = 3,
    train_ratio: float = 0.60,
    test_ratio: float = 0.20,
    purge_minutes: int = 60,
    evaluator: Callable[[pd.DataFrame, pd.DataFrame], object],
) -> WalkForwardTradingReport:
    """Evaluate each future test window without future data in training."""

    if not callable(evaluator):
        raise TypeError("evaluator must be callable")

    windows = generate_windows(
        data,
        folds=folds,
        train_ratio=train_ratio,
        test_ratio=test_ratio,
        purge_minutes=purge_minutes,
    )
    timestamps = pd.to_datetime(
        data["timestamp"], utc=True, errors="raise"
    )

    results: list[object] = []
    for window in windows:
        train_mask = timestamps <= window.train_end
        test_mask = (
            (timestamps >= window.test_start)
            & (timestamps <= window.test_end)
        )
        train = data.loc[train_mask].copy(deep=True)
        test = data.loc[test_mask].copy(deep=True)

        if train.empty or test.empty:
            raise RuntimeError(
                "walk-forward window produced an empty partition"
            )
        if train["timestamp"].max() >= test["timestamp"].min():
            raise RuntimeError(
                "walk-forward leakage detected: training reaches test period"
            )

        test_snapshot = test.copy(deep=True)
        result = evaluator(train, test)

        if not test.equals(test_snapshot):
            raise RuntimeError(
                f"walk-forward evaluator mutated test partition in fold "
                f"{window.fold_id}"
            )
        results.append(result)

    if len(results) != len(windows):
        raise RuntimeError(
            "walk-forward evaluation did not produce one result per window"
        )

    return WalkForwardTradingReport(
        windows=windows,
        results=tuple(results),
    )
