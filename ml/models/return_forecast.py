"""Baseline return-forecasting models for Prediction Bot.

These models estimate future returns only. They do not emit trade actions,
position sizes, risk authorization, or orders.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge


@dataclass(frozen=True, slots=True)
class ReturnForecastConfig:
    """Configuration shared by the baseline return forecasters."""

    model_family: str = "ridge"
    alpha: float = 1.0
    n_estimators: int = 300
    max_depth: int | None = 8
    min_samples_leaf: int = 5
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.model_family not in {"ridge", "random_forest"}:
            raise ValueError("model_family must be 'ridge' or 'random_forest'")
        if self.alpha <= 0:
            raise ValueError("alpha must be greater than zero")
        if self.n_estimators <= 0:
            raise ValueError("n_estimators must be greater than zero")
        if self.max_depth is not None and self.max_depth <= 0:
            raise ValueError("max_depth must be greater than zero")
        if self.min_samples_leaf <= 0:
            raise ValueError("min_samples_leaf must be greater than zero")


class ReturnForecastModel:
    """Thin model-neutral wrapper around Ridge or RandomForestRegressor."""

    def __init__(self, config: ReturnForecastConfig | None = None) -> None:
        self.config = config or ReturnForecastConfig()
        if self.config.model_family == "ridge":
            self._model = Ridge(alpha=self.config.alpha)
        else:
            self._model = RandomForestRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                min_samples_leaf=self.config.min_samples_leaf,
                random_state=self.config.random_state,
                n_jobs=self.config.n_estimators and -1,
            )
        self._fitted = False
        self._feature_count: int | None = None
        self._residual_std: float | None = None

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def feature_count(self) -> int:
        if not self._fitted or self._feature_count is None:
            raise RuntimeError("ReturnForecastModel has not been fitted")
        return self._feature_count

    @property
    def residual_std(self) -> float:
        if not self._fitted or self._residual_std is None:
            raise RuntimeError("ReturnForecastModel has not been fitted")
        return self._residual_std

    def fit(self, X: np.ndarray, y: pd.Series | np.ndarray) -> "ReturnForecastModel":
        X_array = self._validate_X(X)
        y_array = self._validate_y(y)
        if len(X_array) != len(y_array):
            raise ValueError("X and y must contain the same number of rows")
        self._model.fit(X_array, y_array)
        predictions = np.asarray(self._model.predict(X_array), dtype=float)
        residuals = y_array - predictions
        residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
        if not np.isfinite(residual_std):
            raise ValueError("fitted residual uncertainty is non-finite")
        self._feature_count = X_array.shape[1]
        self._residual_std = residual_std
        self._fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("ReturnForecastModel must be fitted before prediction")
        values = np.asarray(self._model.predict(self._validate_X(X)), dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("return forecast contains non-finite values")
        return values

    def predict_frame(
        self,
        X: np.ndarray,
        *,
        timestamp: pd.Series,
        symbol: pd.Series,
        horizon_minutes: int,
    ) -> pd.DataFrame:
        if horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be greater than zero")
        values = self.predict(X)
        if len(timestamp) != len(values) or len(symbol) != len(values):
            raise ValueError("timestamp, symbol, and X must contain the same number of rows")
        ts = pd.to_datetime(timestamp, utc=True, errors="raise")
        if ts.isna().any():
            raise ValueError("timestamp contains invalid values")
        return pd.DataFrame(
            {
                "timestamp": ts.to_numpy(),
                "symbol": symbol.astype(str).to_numpy(),
                "horizon_minutes": horizon_minutes,
                "expected_return": values,
                "uncertainty": self.residual_std,
            },
            index=timestamp.index,
        )

    @staticmethod
    def _validate_X(X: np.ndarray) -> np.ndarray:
        if not isinstance(X, np.ndarray):
            raise TypeError("X must be a numpy ndarray")
        values = np.asarray(X, dtype=float)
        if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
            raise ValueError("X must be a non-empty two-dimensional array")
        if not np.isfinite(values).all():
            raise ValueError("X must contain only finite values")
        return values

    @staticmethod
    def _validate_y(y: pd.Series | np.ndarray) -> np.ndarray:
        if isinstance(y, pd.Series):
            values = y.to_numpy(dtype=float)
        elif isinstance(y, np.ndarray):
            values = np.asarray(y, dtype=float)
        else:
            raise TypeError("y must be a pandas Series or numpy ndarray")
        if values.ndim != 1 or len(values) == 0:
            raise ValueError("y must be a non-empty one-dimensional array")
        if not np.isfinite(values).all():
            raise ValueError("y must contain only finite values")
        return values
