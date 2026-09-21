"""AB-43 final out-of-sample evaluation contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import TemporalSplit, TemporalSplitConfig, temporal_split


@dataclass(frozen=True, slots=True)
class OOSReport:
    """Immutable final out-of-sample evaluation report."""

    train_rows: int
    validation_rows: int
    test_rows: int
    train_end: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    predictions: pd.DataFrame
    test_data: pd.DataFrame


def evaluate_oos(
    dataset: TrainingDataset,
    *,
    config: TemporalSplitConfig | None = None,
    predictor: Callable[
        [pd.DataFrame, pd.DataFrame],
        pd.Series,
    ],
) -> OOSReport:
    """Evaluate a frozen predictor on the untouched temporal test set.

    `predictor(train, test)` receives the training partition and the
    untouched test partition. It must not mutate either partition.
    """

    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")

    if not callable(predictor):
        raise TypeError("predictor must be callable")

    split: TemporalSplit = temporal_split(
        dataset,
        config=config,
    )

    train = split.train.data.copy()
    validation = split.validation.data.copy()
    test = split.test.data.copy()

    predictions = predictor(
        pd.concat(
            [train, validation],
            ignore_index=True,
        ),
        test.copy(),
    )

    if not isinstance(predictions, pd.Series):
        raise TypeError("predictor must return a pandas Series")

    if len(predictions) != len(test):
        raise ValueError(
            "predictor must return exactly one prediction per test row"
        )

    return OOSReport(
        train_rows=len(train),
        validation_rows=len(validation),
        test_rows=len(test),
        train_end=split.train_end,
        validation_end=split.validation_end,
        test_start=split.test_start,
        predictions=predictions.reset_index(drop=True),
        test_data=test.reset_index(drop=True),
    )
