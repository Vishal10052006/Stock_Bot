import pandas as pd

from backtesting.walk_forward import (
    evaluate_walk_forward,
    generate_windows,
)


def _data() -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=60,
        freq="5min",
        tz="Asia/Kolkata",
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * len(timestamps),
            "value": range(len(timestamps)),
        }
    )


def test_walk_forward_windows_are_chronological() -> None:
    windows = generate_windows(
        _data(),
        folds=3,
        purge_minutes=5,
    )

    assert len(windows) == 3

    for window in windows:
        assert window.train_end < window.test_start


def test_walk_forward_evaluator_receives_future_test_only() -> None:
    data = _data()

    def evaluator(
        train: pd.DataFrame,
        test: pd.DataFrame,
    ):
        assert (
            train["timestamp"].max()
            < test["timestamp"].min()
        )

        return len(test)

    report = evaluate_walk_forward(
        data,
        folds=3,
        purge_minutes=5,
        evaluator=evaluator,
    )

    assert len(report.results) == len(
        report.windows
    )
