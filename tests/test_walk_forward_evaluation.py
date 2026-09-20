"""AB-33 walk-forward evaluator tests."""
from __future__ import annotations

import pandas as pd
import pytest

from ml.datasets.models import TrainingDataset
from ml.evaluation.walk_forward import evaluate_walk_forward
from ml.preprocessing.models import BOOLEAN_FEATURES, NUMERIC_FEATURES


def _dataset(rows: int = 72) -> TrainingDataset:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00+05:30",
        periods=rows,
        freq="5min",
    )
    data: dict[str, object] = {
        "timestamp": timestamps,
        "symbol": ["RELIANCE"] * rows,
    }

    for index, column in enumerate(NUMERIC_FEATURES):
        data[column] = [(index + row + 1) / 1000.0 for row in range(rows)]

    for index, column in enumerate(sorted(BOOLEAN_FEATURES)):
        data[column] = [bool((index + row) % 2) for row in range(rows)]

    data["label"] = [
        ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")[row % 3]
        for row in range(rows)
    ]

    features = tuple(
        column for column in data
        if column not in {"timestamp", "symbol", "label"}
    )
    return TrainingDataset(
        data=pd.DataFrame(data),
        feature_columns=features,
    )


def test_ab33_walk_forward_is_chronological_and_oos() -> None:
    report = evaluate_walk_forward(
        _dataset(),
        folds=3,
    )

    assert len(report.folds) == 3
    assert all(
        fold.train_end < fold.validation_start
        for fold in report.folds
    )
    assert all(
        fold.validation_rows > 0 and fold.train_rows > 0
        for fold in report.folds
    )
    assert 0.0 <= report.mean_accuracy <= 1.0
    assert report.mean_log_loss >= 0.0


def test_ab33_requires_enough_history() -> None:
    with pytest.raises(ValueError, match="unique timestamps"):
        evaluate_walk_forward(
            _dataset(rows=12),
            folds=3,
        )
