"""Tests for Phase 9 stratified out-of-sample evaluation."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.evaluation.stratified import evaluate_by_column


def _inputs() -> tuple[pd.Series, pd.DataFrame, pd.DataFrame]:
    """Create deterministic three-class predictions and metadata."""
    y_true = pd.Series([
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
        "LONG_SUCCESS",
    ])

    probabilities = pd.DataFrame(
        [
            [0.8, 0.1, 0.1],
            [0.1, 0.8, 0.1],
            [0.1, 0.1, 0.8],
            [0.7, 0.2, 0.1],
        ],
        columns=["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"],
    )

    metadata = pd.DataFrame(
        {
            "regime": ["TREND_UP", "RANGE", "TREND_UP", "RANGE"],
            "symbol": ["AAA", "AAA", "BBB", "BBB"],
        }
    )

    return y_true, probabilities, metadata


def test_evaluate_by_column_returns_deterministic_sorted_slices() -> None:
    """Each metadata value receives an independent metric report."""
    y_true, probabilities, metadata = _inputs()

    results = evaluate_by_column(
        y_true,
        probabilities,
        metadata,
        column="regime",
    )

    assert [result.key for result in results] == ["RANGE", "TREND_UP"]
    assert [result.metrics["sample_count"] for result in results] == [2, 2]
    assert all("brier_score" in result.metrics for result in results)
    assert all(
        "expected_calibration_error" in result.metrics
        for result in results
    )


def test_evaluate_by_column_excludes_missing_metadata_values() -> None:
    """Missing metadata must not become a fake "nan" category."""
    y_true, probabilities, metadata = _inputs()
    metadata.loc[1, "regime"] = None

    results = evaluate_by_column(
        y_true,
        probabilities,
        metadata,
        column="regime",
    )

    assert [result.key for result in results] == ["TREND_UP"]
    assert results[0].metrics["sample_count"] == 2


def test_evaluate_by_column_rejects_length_mismatch() -> None:
    """Metadata and prediction rows must remain positionally aligned."""
    y_true, probabilities, metadata = _inputs()

    with pytest.raises(ValueError, match="equal lengths"):
        evaluate_by_column(
            y_true.iloc[:-1],
            probabilities,
            metadata,
            column="regime",
        )


def test_evaluate_by_column_rejects_unknown_metadata_column() -> None:
    """The requested stratification dimension must exist."""
    y_true, probabilities, metadata = _inputs()

    with pytest.raises(ValueError, match="missing required column"):
        evaluate_by_column(
            y_true,
            probabilities,
            metadata,
            column="missing",
        )
