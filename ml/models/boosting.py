"""Optional advanced multiclass model adapters for Prediction Bot.

XGBoost and LightGBM are optional dependencies.  The module does not import
either package at module import time, so the baseline installation remains
lightweight and deterministic.  These adapters implement the same fit /
predict_proba boundary as the Phase 9 baseline models.

They estimate outcome probabilities only.  They do not contain strategy or
execution logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib

import numpy as np
import pandas as pd

from ml.models.logistic import MODEL_CLASSES


@dataclass(frozen=True, slots=True)
class BoostingConfig:
    """Configuration shared by optional gradient-boosting backends."""

    backend: str
    n_estimators: int = 300
    learning_rate: float = 0.05
    max_depth: int = 6
    random_state: int = 42

    def __post_init__(self) -> None:
        if self.backend not in {"xgboost", "lightgbm"}:
            raise ValueError("backend must be 'xgboost' or 'lightgbm'")
        if self.n_estimators <= 0:
            raise ValueError("n_estimators must be greater than zero")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be greater than zero")
        if self.max_depth <= 0:
            raise ValueError("max_depth must be greater than zero")


class OptionalBoostingOutcomeModel:
    """Lazy-loading XGBoost/LightGBM multiclass probability model."""

    def __init__(self, config: BoostingConfig) -> None:
        self.config = config
        self._model = None
        self._fitted = False
        self._feature_count: int | None = None

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def feature_count(self) -> int:
        if not self._fitted or self._feature_count is None:
            raise RuntimeError("OptionalBoostingOutcomeModel is not fitted")
        return self._feature_count

    def _build_model(self):
        if self.config.backend == "xgboost":
            try:
                module = importlib.import_module("xgboost")
            except ImportError as exc:
                raise ImportError(
                    "xgboost is required for backend='xgboost'; "
                    "install it as an optional dependency"
                ) from exc
            return module.XGBClassifier(
                objective="multi:softprob",
                num_class=len(MODEL_CLASSES),
                n_estimators=self.config.n_estimators,
                learning_rate=self.config.learning_rate,
                max_depth=self.config.max_depth,
                random_state=self.config.random_state,
                eval_metric="mlogloss",
                n_jobs=1,
            )

        try:
            module = importlib.import_module("lightgbm")
        except ImportError as exc:
            raise ImportError(
                "lightgbm is required for backend='lightgbm'; "
                "install it as an optional dependency"
            ) from exc
        return module.LGBMClassifier(
            objective="multiclass",
            num_class=len(MODEL_CLASSES),
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            random_state=self.config.random_state,
            verbosity=-1,
            n_jobs=1,
        )

    def fit(self, X: np.ndarray, y: pd.Series | np.ndarray) -> "OptionalBoostingOutcomeModel":
        X_array = self._validate_X(X)
        y_array = self._validate_y(y)
        if len(X_array) != len(y_array):
            raise ValueError("X and y must contain the same number of rows")
        missing = set(MODEL_CLASSES) - set(y_array)
        if missing:
            raise ValueError(f"training data is missing classes: {sorted(missing)}")

        class_to_index = {label: index for index, label in enumerate(MODEL_CLASSES)}
        encoded = np.asarray([class_to_index[str(value)] for value in y_array], dtype=int)
        self._model = self._build_model()
        self._model.fit(X_array, encoded)
        self._feature_count = X_array.shape[1]
        self._fitted = True
        return self

    def predict_proba(self, X: np.ndarray) -> pd.DataFrame:
        if not self._fitted or self._model is None:
            raise RuntimeError("OptionalBoostingOutcomeModel must be fitted before prediction")
        values = self._model.predict_proba(self._validate_X(X))
        values = np.asarray(values, dtype=float)
        if values.ndim != 2 or values.shape[1] != len(MODEL_CLASSES):
            raise ValueError("boosting model returned an invalid probability shape")
        if not np.isfinite(values).all():
            raise ValueError("boosting model produced non-finite probabilities")
        if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
            raise ValueError("boosting probabilities must sum to 1")
        return pd.DataFrame(values, columns=list(MODEL_CLASSES))

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
            values = y.to_numpy()
        elif isinstance(y, np.ndarray):
            values = y
        else:
            raise TypeError("y must be a pandas Series or numpy ndarray")
        if values.ndim != 1 or len(values) == 0:
            raise ValueError("y must be a non-empty one-dimensional array")
        values = values.astype(str)
        invalid = set(values) - set(MODEL_CLASSES)
        if invalid:
            raise ValueError(f"y contains invalid labels: {sorted(invalid)}")
        return values
