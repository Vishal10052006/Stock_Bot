"""Tests for Phase 9 baseline, stratified, and dependence diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.evaluation.baselines import (
    class_prior_probabilities,
    majority_class,
    majority_probabilities,
)
from ml.evaluation.effective_sample import diagnose_effective_sample


def test_majority_baseline_uses_canonical_tie_break() -> None:
    y = pd.Series(["NO_EDGE", "LONG_SUCCESS", "SHORT_SUCCESS"])
    assert majority_class(y) == "LONG_SUCCESS"


def test_baseline_probability_rows_sum_to_one() -> None:
    y = pd.Series(["LONG_SUCCESS", "LONG_SUCCESS", "NO_EDGE"])
    probabilities = class_prior_probabilities(y, rows=4)
    assert list(probabilities.columns) == [
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    ]
    assert np.allclose(probabilities.sum(axis=1), 1.0)


def test_majority_probability_is_one_hot() -> None:
    y = pd.Series(["NO_EDGE", "NO_EDGE", "LONG_SUCCESS"])
    probabilities = majority_probabilities(y, rows=3)
    assert np.allclose(probabilities["NO_EDGE"], 1.0)


def test_effective_sample_diagnostic_reports_overlap() -> None:
    data = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01 09:15",
                periods=3,
                freq="5min",
                tz="UTC",
            ),
            "symbol": ["A", "A", "A"],
        }
    )
    diagnostics = diagnose_effective_sample(
        data,
        label_horizon_minutes=60,
    )
    assert diagnostics.observations == 3
    assert diagnostics.overlap_warning is True
