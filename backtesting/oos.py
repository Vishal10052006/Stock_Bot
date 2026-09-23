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
    predictions: pd.Series
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

    The predictor receives a copy of train+validation as its fitting
    context and a separate copy of the test partition for inference.
    The test partition is never concatenated into the predictor's
    training input by this boundary.
    """

    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")

    if not callable(predictor):
        raise TypeError("predictor must be callable")

    split: TemporalSplit = temporal_split(
        dataset,
        config=config,
    )

    train = split.train.data.copy(deep=True)
    validation = split.validation.data.copy(deep=True)
    test = split.test.data.copy(deep=True)

    training_context = pd.concat(
        [train, validation],
        ignore_index=True,
    )

    # Keep an immutable-by-contract snapshot so a predictor cannot
    # mutate the evaluation partition without the boundary detecting it.
    test_snapshot = test.copy(deep=True)

    predictions = predictor(
        training_context,
        test.copy(deep=True),
    )

    if not isinstance(predictions, pd.Series):
        raise TypeError("predictor must return a pandas Series")

    if len(predictions) != len(test):
        raise ValueError(
            "predictor must return exactly one prediction per test row"
        )

    if not test.equals(test_snapshot):
        raise RuntimeError(
            "predictor mutated the out-of-sample test partition"
        )

    if not training_context.empty and not test.empty:
        if training_context["timestamp"].max() >= test["timestamp"].min():
            raise RuntimeError(
                "OOS leakage detected: training context reaches test period"
            )

    return OOSReport(
        train_rows=len(train),
        validation_rows=len(validation),
        test_rows=len(test),
        train_end=split.train_end,
        validation_end=split.validation_end,
        test_start=split.test_start,
        predictions=predictions.reset_index(drop=True).copy(),
        test_data=test.reset_index(drop=True).copy(),
    )
