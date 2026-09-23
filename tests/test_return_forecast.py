import numpy as np
import pandas as pd
import pytest

from ml.models.return_forecast import ReturnForecastConfig, ReturnForecastModel
from ml.prediction.contracts import PredictionProvenance
from ml.prediction.multi_horizon import MultiHorizonReturnForecaster


def _provenance() -> PredictionProvenance:
    return PredictionProvenance(
        model_version="return-v1",
        model_family="ridge",
        dataset_version="dataset-v1",
        feature_version="features-v1",
        target_version="returns-v1",
        code_version="test",
    )


def test_return_forecast_model_predicts_finite_returns_and_uncertainty() -> None:
    X = np.arange(40, dtype=float).reshape(20, 2)
    y = 0.001 * X[:, 0] - 0.002 * X[:, 1]
    model = ReturnForecastModel(ReturnForecastConfig(model_family="ridge"))
    model.fit(X, y)

    predictions = model.predict(X[:4])

    assert predictions.shape == (4,)
    assert np.isfinite(predictions).all()
    assert model.residual_std >= 0.0


def test_return_forecast_rejects_invalid_targets() -> None:
    X = np.ones((3, 2))
    y = np.array([0.1, np.nan, 0.2])
    with pytest.raises(ValueError, match="finite"):
        ReturnForecastModel().fit(X, y)


def test_multi_horizon_forecaster_keeps_horizons_distinct() -> None:
    X = np.arange(60, dtype=float).reshape(30, 2)
    targets = {
        15: pd.Series(0.001 * X[:, 0]),
        60: pd.Series(0.002 * X[:, 1]),
    }
    forecaster = MultiHorizonReturnForecaster((15, 60))
    forecaster.fit(X, targets)

    result = forecaster.predict(
        X[:1],
        timestamp=pd.Timestamp("2026-09-23T09:15:00+05:30"),
        symbol="RELIANCE",
        provenance=_provenance(),
    )

    assert tuple(item.horizon_minutes for item in result.forecasts) == (15, 60)
    assert all(np.isfinite(item.expected_return) for item in result.forecasts)
    assert all(item.uncertainty is not None for item in result.forecasts)


def test_multi_horizon_requires_fit() -> None:
    forecaster = MultiHorizonReturnForecaster((15, 60))
    with pytest.raises(RuntimeError, match="fitted"):
        forecaster.predict(
            np.ones((1, 2)),
            timestamp=pd.Timestamp("2026-09-23T09:15:00+05:30"),
            symbol="RELIANCE",
            provenance=_provenance(),
        )
