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


def test_return_forecast_conformal_calibration_uses_held_out_data() -> None:
    X_train = np.arange(60, dtype=float).reshape(30, 2)
    y_train = 0.001 * X_train[:, 0] - 0.002 * X_train[:, 1]

    X_cal = np.arange(60, 100, dtype=float).reshape(20, 2)
    y_cal = 0.001 * X_cal[:, 0] - 0.002 * X_cal[:, 1] + 0.01

    model = ReturnForecastModel(ReturnForecastConfig(model_family="ridge"))
    model.fit(X_train, y_train)

    assert not model.is_calibrated
    with pytest.raises(RuntimeError, match="conformal-calibrated"):
        model.predict_interval(X_cal)

    model.calibrate(X_cal, y_cal, confidence=0.90)

    assert model.is_calibrated
    assert model.conformal_confidence == 0.90
    assert model.conformal_radius >= 0.0

    lower, upper = model.predict_interval(X_cal[:3])
    predictions = model.predict(X_cal[:3])
    assert np.all(lower <= predictions)
    assert np.all(predictions <= upper)


def test_return_forecast_calibration_validates_confidence_and_feature_count() -> None:
    X = np.ones((5, 2))
    y = np.arange(5, dtype=float)
    model = ReturnForecastModel().fit(X, y)

    with pytest.raises(ValueError, match="confidence"):
        model.calibrate(X, y, confidence=1.0)

    with pytest.raises(ValueError, match="feature count"):
        model.calibrate(np.ones((3, 3)), np.ones(3))


def test_predict_frame_exposes_calibrated_interval() -> None:
    X = np.arange(40, dtype=float).reshape(20, 2)
    y = 0.001 * X[:, 0] - 0.002 * X[:, 1]
    model = ReturnForecastModel().fit(X, y)
    model.calibrate(X[-5:], y[-5:])

    frame = model.predict_frame(
        X[:3],
        timestamp=pd.Series(pd.date_range("2026-09-23", periods=3, freq="5min", tz="UTC")),
        symbol=pd.Series(["RELIANCE"] * 3),
        horizon_minutes=15,
    )

    assert {
        "prediction_interval_lower",
        "prediction_interval_upper",
        "interval_confidence",
    }.issubset(frame.columns)
    assert np.isfinite(frame["prediction_interval_lower"]).all()
    assert np.isfinite(frame["prediction_interval_upper"]).all()


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
