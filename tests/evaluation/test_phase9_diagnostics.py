"""Tests for Phase 9 stratified prediction diagnostics."""

from __future__ import annotations

import pandas as pd

from scripts.run_phase9_experiment import (
    _prediction_diagnostics,
    _stratified_report,
)


def _probabilities() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "LONG_SUCCESS": [0.8, 0.1, 0.2, 0.1],
            "SHORT_SUCCESS": [0.1, 0.8, 0.2, 0.1],
            "NO_EDGE": [0.1, 0.1, 0.6, 0.8],
        }
    )


def test_prediction_diagnostics_reports_distribution_and_per_class_metrics() -> None:
    y = pd.Series(
        [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
            "NO_EDGE",
        ]
    )

    diagnostics = _prediction_diagnostics(y, _probabilities())

    assert diagnostics["predicted_class_distribution"] == {
        "LONG_SUCCESS": 1,
        "SHORT_SUCCESS": 1,
        "NO_EDGE": 2,
    }
    assert set(diagnostics["per_class"]) == {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }


def test_stratified_report_is_out_of_sample_slice_only() -> None:
    y = pd.Series(
        [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
            "NO_EDGE",
        ]
    )
    metadata = pd.DataFrame(
        {
            "regime": ["TREND", "TREND", "RANGE", "RANGE"],
            "symbol": ["AAA", "AAA", "BBB", "BBB"],
            "date": [
                "2026-09-11",
                "2026-09-11",
                "2026-09-12",
                "2026-09-12",
            ],
        }
    )

    report = _stratified_report(y, _probabilities(), metadata)

    assert set(report) == {"regime", "symbol", "date"}
    assert set(report["regime"]) == {"TREND", "RANGE"}
    assert set(report["symbol"]) == {"AAA", "BBB"}
    assert set(report["date"]) == {"2026-09-11", "2026-09-12"}
