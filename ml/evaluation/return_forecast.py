"""Evaluation metrics for chronological return forecasts.

These metrics evaluate predictive return quality only. They do not evaluate
trading profitability or produce strategy decisions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def evaluate_return_forecasts(
    actual: pd.Series | np.ndarray,
    predicted: pd.Series | np.ndarray,
) -> dict[str, float | int]:
    """Evaluate point return forecasts with scale and directional metrics."""
    y_true = _validate_vector(actual, "actual")
    y_pred = _validate_vector(predicted, "predicted")
    if len(y_true) != len(y_pred):
        raise ValueError("actual and predicted must contain the same number of rows")

    errors = y_pred - y_true
    abs_errors = np.abs(errors)
    squared_errors = errors**2

    return {
        "sample_count": int(len(y_true)),
        "mae": float(np.mean(abs_errors)),
        "rmse": float(np.sqrt(np.mean(squared_errors))),
        "mean_error": float(np.mean(errors)),
        "actual_mean": float(np.mean(y_true)),
        "predicted_mean": float(np.mean(y_pred)),
        "actual_std": float(np.std(y_true)),
        "predicted_std": float(np.std(y_pred)),
        "directional_accuracy": float(
            np.mean(np.sign(y_pred) == np.sign(y_true))
        ),
        "positive_return_rate_actual": float(np.mean(y_true > 0.0)),
        "positive_return_rate_predicted": float(np.mean(y_pred > 0.0)),
    }


def evaluate_prediction_intervals(
    actual: pd.Series | np.ndarray,
    lower: pd.Series | np.ndarray,
    upper: pd.Series | np.ndarray,
    *,
    confidence_level: float,
) -> dict[str, float | int]:
    """Evaluate empirical coverage and width of a prediction interval."""
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must lie in (0, 1)")

    y_true = _validate_vector(actual, "actual")
    lower_values = _validate_vector(lower, "lower")
    upper_values = _validate_vector(upper, "upper")

    if not (len(y_true) == len(lower_values) == len(upper_values)):
        raise ValueError("actual, lower, and upper must have the same number of rows")
    if (lower_values > upper_values).any():
        raise ValueError("lower interval values must not exceed upper values")

    covered = (y_true >= lower_values) & (y_true <= upper_values)
    widths = upper_values - lower_values

    return {
        "sample_count": int(len(y_true)),
        "confidence_level": float(confidence_level),
        "empirical_coverage": float(np.mean(covered)),
        "coverage_gap": float(np.mean(covered) - confidence_level),
        "mean_interval_width": float(np.mean(widths)),
        "median_interval_width": float(np.median(widths)),
        "min_interval_width": float(np.min(widths)),
        "max_interval_width": float(np.max(widths)),
    }


def evaluate_return_forecasts_by_column(
    frame: pd.DataFrame,
    *,
    actual_column: str = "actual_return",
    predicted_column: str = "predicted_return",
    group_column: str,
) -> dict[str, dict[str, float | int]]:
    """Evaluate return forecasts independently for each metadata group."""
    required = {actual_column, predicted_column, group_column}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("frame must not be empty")

    result: dict[str, dict[str, float | int]] = {}
    for key, group in frame.groupby(group_column, dropna=False, sort=True):
        result[str(key)] = evaluate_return_forecasts(
            group[actual_column],
            group[predicted_column],
        )
    return result


def _validate_vector(
    values: pd.Series | np.ndarray,
    name: str,
) -> np.ndarray:
    if isinstance(values, pd.Series):
        array = values.to_numpy(dtype=float)
    elif isinstance(values, np.ndarray):
        array = np.asarray(values, dtype=float)
    else:
        raise TypeError(f"{name} must be a pandas Series or numpy ndarray")

    if array.ndim != 1 or len(array) == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array
