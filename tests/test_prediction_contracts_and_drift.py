import pandas as pd
import pytest

from ml.prediction.contracts import (
    ClassificationPrediction,
    MultiHorizonForecast,
    PredictionProvenance,
    ReturnForecast,
)
from ml.prediction.drift import compare_prediction_distributions


def _provenance() -> PredictionProvenance:
    return PredictionProvenance(
        model_version="v1",
        model_family="logistic",
        dataset_version="d1",
        feature_version="f1",
        target_version="t1",
        code_version="c1",
    )


def _probabilities() -> dict[str, float]:
    return {
        "LONG_SUCCESS": 0.4,
        "SHORT_SUCCESS": 0.2,
        "NO_EDGE": 0.4,
    }


def test_classification_prediction_is_causal_contract() -> None:
    prediction = ClassificationPrediction(
        timestamp=pd.Timestamp("2026-09-23 10:00:00+05:30"),
        symbol="RELIANCE",
        probabilities=_probabilities(),
        provenance=_provenance(),
    )
    assert prediction.symbol == "RELIANCE"


def test_return_forecast_rejects_invalid_horizon() -> None:
    with pytest.raises(ValueError, match="horizon_minutes"):
        ReturnForecast(
            timestamp=pd.Timestamp("2026-09-23 10:00:00+05:30"),
            symbol="RELIANCE",
            horizon_minutes=0,
            expected_return=0.01,
            uncertainty=None,
            provenance=_provenance(),
        )


def test_multi_horizon_requires_unique_horizons() -> None:
    base = dict(
        timestamp=pd.Timestamp("2026-09-23 10:00:00+05:30"),
        symbol="RELIANCE",
        expected_return=0.01,
        uncertainty=0.02,
        provenance=_provenance(),
    )
    first = ReturnForecast(horizon_minutes=5, **base)
    second = ReturnForecast(horizon_minutes=5, **base)
    with pytest.raises(ValueError, match="unique"):
        MultiHorizonForecast((first, second))


def test_prediction_drift_report() -> None:
    reference = pd.DataFrame(
        [
            _probabilities(),
            {"LONG_SUCCESS": 0.5, "SHORT_SUCCESS": 0.2, "NO_EDGE": 0.3},
        ]
    )
    current = pd.DataFrame(
        [
            {"LONG_SUCCESS": 0.7, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.2},
            {"LONG_SUCCESS": 0.8, "SHORT_SUCCESS": 0.1, "NO_EDGE": 0.1},
        ]
    )
    report = compare_prediction_distributions(reference, current)
    assert report.sample_count_reference == 2
    assert report.sample_count_current == 2
    assert set(report.probability_psi) == {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }
