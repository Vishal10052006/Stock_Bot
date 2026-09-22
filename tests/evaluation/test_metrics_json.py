"""Tests for JSON-safe Phase 9 evaluation metrics."""

from __future__ import annotations

import json

import pandas as pd

from ml.evaluation.metrics import evaluate_predictions
from scripts.run_phase9_experiment import _metrics


def test_confusion_matrix_is_json_serializable() -> None:
    y_true = pd.Series(
        ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE", "NO_EDGE"]
    )
    probabilities = pd.DataFrame(
        {
            "LONG_SUCCESS": [0.8, 0.1, 0.2, 0.1],
            "SHORT_SUCCESS": [0.1, 0.8, 0.2, 0.1],
            "NO_EDGE": [0.1, 0.1, 0.6, 0.8],
        }
    )

    result = evaluate_predictions(y_true, probabilities)

    assert result["confusion_matrix"].tolist() == [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 2],
    ]

    report_metrics = _metrics(y_true, probabilities)
    assert report_metrics["confusion_matrix"] == [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 2],
    ]
    json.dumps(report_metrics)
