import pandas as pd
import pytest

from ml.prediction.contracts import (
    ClassificationPrediction,
    PredictionProvenance,
    ReturnForecast,
)
from ml.prediction.ensemble import (
    EnsembleComponent,
    PredictionEnsembler,
)


def _provenance(version: str) -> PredictionProvenance:
    return PredictionProvenance(
        model_version=version,
        model_family="test",
        dataset_version="d1",
        feature_version="f1",
        target_version="t1",
        code_version="c1",
    )


def _classification(version: str, long: float, short: float, no_edge: float) -> ClassificationPrediction:
    return ClassificationPrediction(
        timestamp=pd.Timestamp("2026-09-24 10:00:00+05:30"),
        symbol="RELIANCE",
        probabilities={
            "LONG_SUCCESS": long,
            "SHORT_SUCCESS": short,
            "NO_EDGE": no_edge,
        },
        provenance=_provenance(version),
    )


def _return(version: str, value: float, lower: float = -0.02, upper: float = 0.04) -> ReturnForecast:
    return ReturnForecast(
        timestamp=pd.Timestamp("2026-09-24 10:00:00+05:30"),
        symbol="RELIANCE",
        horizon_minutes=60,
        expected_return=value,
        uncertainty=0.01,
        provenance=_provenance(version),
        interval_lower=lower,
        interval_upper=upper,
        interval_confidence=0.90,
    )


def test_classification_ensemble_is_weighted_and_normalized() -> None:
    ensembler = PredictionEnsembler()
    result = ensembler.combine_classification(
        [
            EnsembleComponent(_classification("a", 0.8, 0.1, 0.1), 1.0),
            EnsembleComponent(_classification("b", 0.2, 0.3, 0.5), 3.0),
        ]
    )

    assert result.probabilities["LONG_SUCCESS"] == pytest.approx(0.35)
    assert result.probabilities["SHORT_SUCCESS"] == pytest.approx(0.25)
    assert result.probabilities["NO_EDGE"] == pytest.approx(0.40)
    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert result.provenance.model_family == "ensemble"


def test_return_ensemble_combines_point_and_uses_interval_envelope() -> None:
    result = PredictionEnsembler().combine_return_forecast(
        [
            EnsembleComponent(_return("ridge", 0.01, -0.01, 0.03), 1.0),
            EnsembleComponent(_return("rf", 0.03, -0.02, 0.04), 1.0),
        ]
    )

    assert result.expected_return == pytest.approx(0.02)
    assert result.interval_lower == pytest.approx(-0.02)
    assert result.interval_upper == pytest.approx(0.04)
    assert result.interval_confidence == pytest.approx(0.90)


def test_ensemble_rejects_mixed_prediction_types() -> None:
    with pytest.raises(TypeError, match="ClassificationPrediction"):
        PredictionEnsembler().combine_classification(
            [
                EnsembleComponent(
                    _return("ridge", 0.01),
                    1.0,
                )
            ]
        )


def test_ensemble_rejects_mismatched_identity() -> None:
    other = _classification("b", 0.4, 0.2, 0.4)
    other = ClassificationPrediction(
        timestamp=other.timestamp + pd.Timedelta(minutes=5),
        symbol=other.symbol,
        probabilities=other.probabilities,
        provenance=other.provenance,
    )
    with pytest.raises(ValueError, match="timestamp and symbol"):
        PredictionEnsembler().combine_classification(
            [
                EnsembleComponent(_classification("a", 0.4, 0.2, 0.4), 1.0),
                EnsembleComponent(other, 1.0),
            ]
        )


def test_ensemble_rejects_mismatched_return_horizon() -> None:
    first = _return("a", 0.01)
    second = ReturnForecast(
        timestamp=first.timestamp,
        symbol=first.symbol,
        horizon_minutes=30,
        expected_return=0.02,
        uncertainty=0.01,
        provenance=_provenance("b"),
    )
    with pytest.raises(ValueError, match="horizon"):
        PredictionEnsembler().combine_return_forecast(
            [
                EnsembleComponent(first, 1.0),
                EnsembleComponent(second, 1.0),
            ]
        )


def test_ensemble_rejects_non_positive_total_weight() -> None:
    with pytest.raises(ValueError, match="positive sum"):
        PredictionEnsembler().combine_classification(
            [EnsembleComponent(_classification("a", 0.4, 0.2, 0.4), 0.0)]
        )


def test_ensemble_is_prediction_only() -> None:
    assert not hasattr(PredictionEnsembler, "trade")
    assert not hasattr(PredictionEnsembler, "order")
    assert not hasattr(PredictionEnsembler, "position_size")
