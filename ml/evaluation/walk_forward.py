"""AB-33 walk-forward evaluation for Phase 9 probability models.

Each fold trains only on timestamps strictly before the validation window,
keeps the existing purge-aware temporal boundaries, and evaluates the fitted
model on later observations without refitting on validation/test data.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import TemporalSplitConfig, temporal_split
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One chronological train/validation evaluation fold."""

    fold_id: int
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    train_rows: int
    validation_rows: int
    accuracy: float
    log_loss: float


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    """Aggregate walk-forward model-quality report."""

    folds: tuple[WalkForwardFold, ...]
    mean_accuracy: float
    mean_log_loss: float


def _log_loss(
    probabilities: pd.DataFrame,
    labels: pd.Series,
) -> float:
    """Calculate multiclass log loss with stable probability clipping."""
    ordered = probabilities.loc[:, ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"]]
    class_to_index = {
        label: index
        for index, label in enumerate(ordered.columns)
    }
    y = labels.astype(str).map(class_to_index).to_numpy()

    values = np.clip(ordered.to_numpy(dtype=float), 1e-12, 1.0)
    return float(
        -np.mean(
            np.log(
                values[
                    np.arange(len(y)),
                    y,
                ]
            )
        )
    )


def evaluate_walk_forward(
    dataset: TrainingDataset,
    *,
    config: TemporalSplitConfig | None = None,
    folds: int = 3,
    model_factory: Callable[[], object] = LogisticOutcomeModel,
) -> WalkForwardReport:
    """Evaluate chronological folds without fitting on future observations.

    Fold boundaries are derived from progressively earlier prefixes. The
    existing temporal splitter remains authoritative for purge behavior.
    """
    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")
    if folds < 1:
        raise ValueError("folds must be at least 1")

    timestamps = (
        dataset.data["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    minimum_timestamps = folds * 10
    if len(timestamps) < minimum_timestamps:
        raise ValueError(
            f"walk-forward evaluation requires at least {minimum_timestamps} "
            "unique timestamps"
        )

    results: list[WalkForwardFold] = []

    # Use expanding chronological prefixes. Each prefix is split by the
    # existing purge-aware splitter; validation remains strictly later than
    # the corresponding training partition.
    usable_prefixes = np.linspace(
        max(3, len(timestamps) // 2),
        len(timestamps),
        num=folds + 1,
        dtype=int,
    )[1:]

    for fold_id, prefix_size in enumerate(usable_prefixes, start=1):
        prefix_times = set(timestamps.iloc[:prefix_size])

        prefix_data = dataset.data[
            dataset.data["timestamp"].isin(prefix_times)
        ].copy()

        split = temporal_split(
            TrainingDataset(
                data=prefix_data,
                feature_columns=dataset.feature_columns,
                label_column=dataset.label_column,
            ),
            config=config,
        )

        preprocessor = FeaturePreprocessor()
        X_train = preprocessor.fit_transform(split.train.X)

        model = model_factory()
        if not hasattr(model, "fit") or not hasattr(model, "predict_proba"):
            raise TypeError("model_factory must produce a fit/predict_proba model")

        model.fit(X_train, split.train.y)

        X_validation = preprocessor.transform(split.validation.X)
        probabilities = model.predict_proba(X_validation)
        predictions = probabilities.idxmax(axis=1)

        accuracy = float(
            (predictions.to_numpy() == split.validation.y.astype(str).to_numpy())
            .mean()
        )
        log_loss = _log_loss(
            probabilities,
            split.validation.y,
        )

        results.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_end=split.train_end,
                validation_start=split.validation_start,
                validation_end=split.validation_end,
                train_rows=len(split.train.data),
                validation_rows=len(split.validation.data),
                accuracy=accuracy,
                log_loss=log_loss,
            )
        )

    return WalkForwardReport(
        folds=tuple(results),
        mean_accuracy=float(np.mean([fold.accuracy for fold in results])),
        mean_log_loss=float(np.mean([fold.log_loss for fold in results])),
    )
