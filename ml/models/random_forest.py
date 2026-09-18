"""Random Forest outcome model for STOCK BOT Phase 9.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 9, First ML Model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ml.labeling.models import PredictionLabel


MODEL_CLASSES: tuple[str, ...] = (
    PredictionLabel.LONG_SUCCESS.value,
    PredictionLabel.SHORT_SUCCESS.value,
    PredictionLabel.NO_EDGE.value,
)


@dataclass(frozen=True)
class RandomForestConfig:
    """Configuration for the Phase 9 Random Forest benchmark."""

    n_estimators: int = 300
    max_depth: int | None = 8
    min_samples_leaf: int = 5
    max_features: str | float | int | None = "sqrt"
    random_state: int = 42
    n_jobs: int = -1

    def __post_init__(self) -> None:
        """Validate Random Forest configuration."""
        if self.n_estimators <= 0:
            raise ValueError("n_estimators must be greater than 0.")
        if self.max_depth is not None and self.max_depth <= 0:
            raise ValueError("max_depth must be greater than 0 when supplied.")
        if self.min_samples_leaf <= 0:
            raise ValueError("min_samples_leaf must be greater than 0.")


class RandomForestOutcomeModel:
    """Auditable wrapper around sklearn RandomForestClassifier."""

    def __init__(self, config: RandomForestConfig | None = None) -> None:
        """Initialize an unfitted Random Forest model."""
        self.config = config or RandomForestConfig()
        self._model = RandomForestClassifier(
            n_estimators=self.config.n_estimators,
            max_depth=self.config.max_depth,
            min_samples_leaf=self.config.min_samples_leaf,
            max_features=self.config.max_features,
            random_state=self.config.random_state,
            n_jobs=self.config.n_jobs,
        )
        self._fitted = False
        self._feature_count: int | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether the model has been fitted."""
        return self._fitted

    @property
    def feature_count(self) -> int:
        """Return the number of fitted input features."""
        if not self._fitted or self._feature_count is None:
            raise RuntimeError("RandomForestOutcomeModel has not been fitted.")
        return self._feature_count

    @property
    def classes(self) -> tuple[str, ...]:
        """Return fitted classes in sklearn order."""
        if not self._fitted:
            raise RuntimeError("RandomForestOutcomeModel has not been fitted.")
        return tuple(str(value) for value in self._model.classes_)

    def fit(
        self,
        X: np.ndarray,
        y: pd.Series | np.ndarray,
    ) -> "RandomForestOutcomeModel":
        """Fit the benchmark model on already-preprocessed training data."""
        X_array = self._validate_X(X)
        y_array = self._validate_y(y)

        if len(X_array) != len(y_array):
            raise ValueError("X and y must contain the same number of rows.")

        missing = set(MODEL_CLASSES) - set(y_array)
        if missing:
            raise ValueError(
                "Training data must contain all three Phase 9 prediction "
                f"classes. Missing classes: {sorted(missing)}"
            )

        self._model.fit(X_array, y_array)
        self._fitted = True
        self._feature_count = X_array.shape[1]
        return self

    def predict_proba(self, X: np.ndarray) -> pd.DataFrame:
        """Return canonical three-class probabilities."""
        if not self._fitted:
            raise RuntimeError(
                "RandomForestOutcomeModel must be fitted before prediction."
            )

        X_array = self._validate_X(X)
        probabilities = self._model.predict_proba(X_array)

        result = pd.DataFrame(
            0.0,
            index=range(len(X_array)),
            columns=list(MODEL_CLASSES),
        )

        for index, model_class in enumerate(self._model.classes_):
            result[str(model_class)] = probabilities[:, index]

        result = result.loc[:, list(MODEL_CLASSES)]
        values = result.to_numpy(dtype=float)

        if not np.isfinite(values).all():
            raise ValueError("Model produced non-finite probabilities.")

        if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
            raise ValueError("Model probabilities must sum to 1.")

        return result

    @staticmethod
    def _validate_X(X: np.ndarray) -> np.ndarray:
        """Validate a preprocessed feature matrix."""
        if not isinstance(X, np.ndarray):
            raise TypeError("X must be a numpy ndarray.")
        if X.ndim != 2 or X.shape[0] == 0 or X.shape[1] == 0:
            raise ValueError("X must be a non-empty two-dimensional array.")

        values = np.asarray(X, dtype=float)

        if not np.isfinite(values).all():
            raise ValueError("X must contain only finite values.")

        return values

    @staticmethod
    def _validate_y(y: pd.Series | np.ndarray) -> np.ndarray:
        """Validate the target labels."""
        if isinstance(y, pd.Series):
            values = y.to_numpy()
        elif isinstance(y, np.ndarray):
            values = y
        else:
            raise TypeError("y must be a pandas Series or numpy ndarray.")

        if values.ndim != 1 or len(values) == 0:
            raise ValueError("y must be a non-empty one-dimensional array.")

        values = values.astype(str)
        invalid = set(values) - set(MODEL_CLASSES)

        if invalid:
            raise ValueError(
                f"y contains invalid prediction labels: {sorted(invalid)}"
            )

        return values
