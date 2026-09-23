import numpy as np
import pandas as pd
import pytest

from ml.evaluation.return_forecast import (
    evaluate_prediction_intervals,
    evaluate_return_forecasts,
    evaluate_return_forecasts_by_column,
)


def test_return_forecast_metrics_are_finite_and_deterministic() -> None:
    actual = pd.Series([0.01, -0.02, 0.03, 0.00])
    predicted = pd.Series([0.02, -0.01, 0.01, -0.01])

    metrics = evaluate_return_forecasts(actual, predicted)

    assert metrics["sample_count"] == 4
    assert metrics["mae"] == pytest.approx(0.01)
    assert metrics["rmse"] == pytest.approx(np.sqrt(0.000175))
    assert metrics["directional_accuracy"] == pytest.approx(0.75)


def test_interval_metrics_report_empirical_coverage() -> None:
    actual = np.array([0.01, 0.20, -0.10, 0.03])
    lower = np.array([-0.02, 0.00, -0.20, 0.00])
    upper = np.array([0.02, 0.10, -0.05, 0.02])

    metrics = evaluate_prediction_intervals(
        actual,
        lower,
        upper,
        confidence_level=0.90,
    )

    assert metrics["sample_count"] == 4
    assert metrics["empirical_coverage"] == pytest.approx(0.5)
    assert metrics["coverage_gap"] == pytest.approx(-0.4)
    assert metrics["mean_interval_width"] == pytest.approx(0.15)


def test_return_forecast_group_metrics() -> None:
    frame = pd.DataFrame(
        {
            "actual_return": [0.01, -0.02, 0.03, -0.01],
            "predicted_return": [0.02, -0.01, 0.01, 0.00],
            "symbol": ["A", "A", "B", "B"],
        }
    )

    result = evaluate_return_forecasts_by_column(
        frame,
        group_column="symbol",
    )

    assert set(result) == {"A", "B"}
    assert result["A"]["sample_count"] == 2
    assert result["B"]["sample_count"] == 2


def test_return_forecast_metrics_reject_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same number"):
        evaluate_return_forecasts(np.array([0.1, 0.2]), np.array([0.1]))


def test_interval_metrics_reject_invalid_interval() -> None:
    with pytest.raises(ValueError, match="lower"):
        evaluate_prediction_intervals(
            np.array([0.1, 0.2]),
            np.array([0.2, 0.0]),
            np.array([0.1, 0.3]),
            confidence_level=0.90,
        )
