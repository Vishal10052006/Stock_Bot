"""Purged walk-forward splitter for research experiments."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_id: int
    train_indices: tuple[int, ...]
    validation_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def build_walk_forward_folds(
    decision_times: list[datetime],
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    purge: timedelta,
    step: int | None = None,
) -> tuple[WalkForwardFold, ...]:
    if not decision_times:
        return ()
    if any(right < left for left, right in zip(decision_times, decision_times[1:])):
        raise ValueError("decision_times must be sorted")
    step = step or test_size
    folds = []
    start = 0
    fold_id = 0

    while start + train_size + validation_size + test_size <= len(decision_times):
        train_end = start + train_size
        validation_start = train_end
        validation_end = validation_start + validation_size
        test_start = validation_end
        test_end = test_start + test_size

        purge_cutoff = decision_times[test_start] - purge
        train_indices = tuple(i for i in range(start, train_end) if decision_times[i] < purge_cutoff)
        validation_indices = tuple(range(validation_start, validation_end))
        test_indices = tuple(range(test_start, test_end))

        folds.append(WalkForwardFold(fold_id, train_indices, validation_indices, test_indices))
        fold_id += 1
        start += step
    return tuple(folds)
