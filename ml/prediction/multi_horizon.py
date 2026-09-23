"""Multi-horizon return forecasting boundary."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ml.models.return_forecast import ReturnForecastConfig, ReturnForecastModel
from ml.prediction.contracts import MultiHorizonForecast, PredictionProvenance, ReturnForecast


@dataclass(slots=True)
class MultiHorizonReturnForecaster:
    """Independent model per horizon with explicit horizon isolation."""

    horizons_minutes: tuple[int, ...]
    config: ReturnForecastConfig = field(default_factory=ReturnForecastConfig)
    _models: dict[int, ReturnForecastModel] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.horizons_minutes:
            raise ValueError("horizons_minutes must not be empty")
        if any(value <= 0 for value in self.horizons_minutes):
            raise ValueError("horizons must be positive")
        if len(set(self.horizons_minutes)) != len(self.horizons_minutes):
            raise ValueError("horizons must be unique")

    def fit(
        self,
        X: np.ndarray,
        targets: dict[int, pd.Series | np.ndarray],
    ) -> "MultiHorizonReturnForecaster":
        missing = set(self.horizons_minutes) - set(targets)
        if missing:
            raise ValueError(f"missing targets for horizons: {sorted(missing)}")
        self._models.clear()
        for horizon in self.horizons_minutes:
            model = ReturnForecastModel(self.config)
            model.fit(X, targets[horizon])
            self._models[horizon] = model
        return self

    def calibrate(
        self,
        X_calibration: np.ndarray,
        targets: dict[int, pd.Series | np.ndarray],
        *,
        confidence: float = 0.90,
    ) -> "MultiHorizonReturnForecaster":
        """Calibrate each horizon independently on a later chronological holdout."""
        if not self._models:
            raise RuntimeError("MultiHorizonReturnForecaster must be fitted before calibration")
        missing = set(self.horizons_minutes) - set(targets)
        if missing:
            raise ValueError(f"missing calibration targets for horizons: {sorted(missing)}")

        for horizon in self.horizons_minutes:
            self._models[horizon].calibrate(
                X_calibration,
                targets[horizon],
                confidence=confidence,
            )
        return self

    def predict(
        self,
        X: np.ndarray,
        *,
        timestamp: pd.Timestamp,
        symbol: str,
        provenance: PredictionProvenance,
    ) -> MultiHorizonForecast:
        if not self._models:
            raise RuntimeError("MultiHorizonReturnForecaster must be fitted before prediction")
        forecasts = []
        for horizon in self.horizons_minutes:
            model = self._models[horizon]
            expected_return = float(model.predict(X[:1])[0])
            interval_lower = interval_upper = interval_confidence = None
            if model.is_calibrated:
                lower, upper = model.predict_interval(X[:1])
                interval_lower = float(lower[0])
                interval_upper = float(upper[0])
                interval_confidence = model.conformal_confidence

            forecasts.append(
                ReturnForecast(
                    timestamp=timestamp,
                    symbol=symbol,
                    horizon_minutes=horizon,
                    expected_return=expected_return,
                    uncertainty=model.residual_std,
                    provenance=provenance,
                    interval_lower=interval_lower,
                    interval_upper=interval_upper,
                    interval_confidence=interval_confidence,
                )
            )
        return MultiHorizonForecast(forecasts=tuple(forecasts))
