from __future__ import annotations

import pandas as pd
import pytest

from ml.prediction.feature_drift import compare_feature_distributions


def test_feature_drift_is_deterministic() -> None:
    reference = pd.DataFrame({"x": [0.0, 0.1, 0.2, 0.3], "y": [1, 1, 2, 2]})
    current = pd.DataFrame({"x": [0.0, 0.1, 0.2, 0.3], "y": [1, 1, 2, 2]})

    report = compare_feature_distributions(reference, current)

    assert report.alert is False
    assert report.alert_features == ()
    assert report.psi_by_feature["x"] == 0.0


def test_feature_drift_detects_shift() -> None:
    reference = pd.DataFrame({"x": [0.0] * 100})
    current = pd.DataFrame({"x": [10.0] * 100})

    report = compare_feature_distributions(
        reference,
        current,
        psi_threshold=0.20,
    )

    assert report.alert is True
    assert report.alert_features == ("x",)


def test_feature_drift_requires_matching_columns() -> None:
    with pytest.raises(ValueError, match="identical"):
        compare_feature_distributions(
            pd.DataFrame({"x": [1.0]}),
            pd.DataFrame({"y": [1.0]}),
        )


def test_feature_drift_rejects_no_finite_values() -> None:
    with pytest.raises(ValueError, match="no finite"):
        compare_feature_distributions(
            pd.DataFrame({"x": [float("nan")]}),
            pd.DataFrame({"x": [1.0]}),
        )
