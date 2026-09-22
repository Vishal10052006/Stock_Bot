import pandas as pd

from backtesting.oos import evaluate_oos
from ml.datasets.models import TrainingDataset


def test_oos_keeps_test_partition_after_training_period() -> None:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=200,
        freq="5min",
        tz="Asia/Kolkata",
    )

    data = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "feature": range(len(timestamps)),
            "label": ["LONG_SUCCESS"] * len(timestamps),
        }
    )

    dataset = TrainingDataset(
        data=data,
        feature_columns=("feature",),
    )

    def predictor(
        train: pd.DataFrame,
        test: pd.DataFrame,
    ) -> pd.Series:
        assert train["timestamp"].max() < test["timestamp"].min()

        return pd.Series(
            ["LONG_SUCCESS"] * len(test)
        )

    report = evaluate_oos(
        dataset,
        predictor=predictor,
    )

    assert report.test_rows > 0

    assert (
        report.train_end
        < report.test_start
    )
