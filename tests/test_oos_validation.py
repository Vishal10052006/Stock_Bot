import pandas as pd
import pytest

from backtesting.oos import evaluate_oos
from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import TemporalSplitConfig


def _dataset() -> TrainingDataset:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=60,
        freq="5min",
        tz="UTC",
    )
    data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "feature": range(len(timestamps)),
            "label": [0, 1] * 30,
        }
    )
    return TrainingDataset(
        data=data,
        feature_columns=("feature",),
    )


def test_oos_test_partition_is_temporally_after_training_context() -> None:
    seen: dict[str, pd.Timestamp] = {}

    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        seen["train_max"] = train["timestamp"].max()
        seen["test_min"] = test["timestamp"].min()
        return pd.Series([0] * len(test))

    report = evaluate_oos(
        _dataset(),
        config=TemporalSplitConfig(purge_minutes=5),
        predictor=predictor,
    )

    assert seen["train_max"] < seen["test_min"]
    assert report.test_rows == len(report.test_data)
    assert report.predictions.index.tolist() == list(range(report.test_rows))


def test_oos_rejects_predictor_mutating_test_partition() -> None:
    def predictor(train: pd.DataFrame, test: pd.DataFrame) -> pd.Series:
        test.loc[:, "feature"] = -1
        return pd.Series([0] * len(test))

    with pytest.raises(
        RuntimeError,
        match="mutated the out-of-sample test partition",
    ):
        evaluate_oos(
            _dataset(),
            config=TemporalSplitConfig(purge_minutes=5),
            predictor=predictor,
        )


def test_oos_uses_supplied_split_configuration() -> None:
    report = evaluate_oos(
        _dataset(),
        config=TemporalSplitConfig(
            train_ratio=0.60,
            validation_ratio=0.20,
            test_ratio=0.20,
            purge_minutes=5,
        ),
        predictor=lambda train, test: pd.Series([0] * len(test)),
    )

    assert report.train_end < report.test_start
    assert report.train_rows > 0
    assert report.validation_rows > 0
    assert report.test_rows > 0
