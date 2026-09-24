import numpy as np
import pandas as pd
import pytest

from scripts.run_phase9_return_forecast_walk_forward import (
    _aggregate_fold_metrics,
    _split_train_for_calibration,
)


def _frame(rows: int = 20) -> pd.DataFrame:
    timestamps = pd.date_range(
        "2026-01-01 09:15:00",
        periods=rows,
        freq="5min",
        tz="Asia/Kolkata",
    )
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ITC"] * rows,
            "future_return": np.linspace(-0.01, 0.01, rows),
        }
    )


def test_walk_forward_training_calibration_split_is_chronological() -> None:
    fit, calibration = _split_train_for_calibration(_frame())

    assert not fit.empty
    assert not calibration.empty
    assert fit["timestamp"].max() < calibration["timestamp"].min()


def test_walk_forward_calibration_split_rejects_tiny_input() -> None:
    frame = _frame(2)

    with pytest.raises(ValueError, match="at least 3"):
        _split_train_for_calibration(frame)


def test_walk_forward_aggregate_is_test_row_weighted() -> None:
    folds = [
        {
            "test_rows": 2,
            "point_forecast": {
                "mae": 0.01,
                "rmse": 0.02,
                "mean_error": 0.0,
                "directional_accuracy": 0.5,
            },
            "interval": {"empirical_coverage": 1.0},
            "zero_return_baseline": {"mae": 0.03},
        },
        {
            "test_rows": 6,
            "point_forecast": {
                "mae": 0.02,
                "rmse": 0.04,
                "mean_error": 0.01,
                "directional_accuracy": 0.75,
            },
            "interval": {"empirical_coverage": 0.8333333333333334},
            "zero_return_baseline": {"mae": 0.04},
        },
    ]

    result = _aggregate_fold_metrics(folds)

    assert result["test_rows"] == 8
    assert result["weighted_mean"]["mae"] == pytest.approx(0.0175)
    assert result["weighted_mean"]["rmse"] == pytest.approx(0.035)
    assert result["weighted_mean"]["directional_accuracy"] == pytest.approx(0.6875)
    assert result["weighted_interval_coverage"] == pytest.approx(0.875)
    assert result["weighted_zero_return_baseline_mae"] == pytest.approx(0.0375)


def test_walk_forward_aggregate_rejects_empty_folds() -> None:
    from scripts.run_phase9_return_forecast_walk_forward import _aggregate_fold_metrics

    with pytest.raises(ValueError, match="at least one"):
        _aggregate_fold_metrics([])
