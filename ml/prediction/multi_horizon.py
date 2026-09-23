"""Multi-horizon return forecasting boundary."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.models.return_forecast import ReturnForecastConfig, ReturnForecastModel
from ml.prediction.contracts import MultiHorizonForecast, PredictionProvenance, ReturnForecast


@dataclass(frozen=True, slots=True)
class MultiHorizonReturnForecaster:
    """Independent model per horizon with explicit horizon isolation."""

    horizons_minutes: tuple[int, ...]
    config: ReturnForecastConfig = ReturnForecastConfig()

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
        self._models = {}
        for horizon in self.horizons_minutes:
            model = ReturnForecastModel(self.config)
            model.fit(X, targets[horizon])
            self._models[horizon] = model
        return self

    def predict(
        self,
        X: np.ndarray,
        *,
        timestamp: pd.Timestamp,
        symbol: str,
        provenance: PredictionProvenance,
    ) -> MultiHorizonForecast:
        if not hasattr(self, "_models"):
            raise RuntimeError("MultiHorizonReturnForecaster must be fitted before prediction")
        forecasts = tuple(
            ReturnForecast(
                timestamp=timestamp,
                symbol=symbol,
                horizon_minutes=horizon,
                expected_return=float(self._models[horizon].predict(X[:1])[0]),
                uncertainty=self._models[horizon].residual_std,
                provenance=provenance,
            )
            for horizon in self.horizons_minutes
        )
        return MultiHorizonForecast(forecasts=forecasts)
