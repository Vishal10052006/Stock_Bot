"""
Logistic Regression model for STOCK BOT Phase 9.

This module defines the model configuration and a small wrapper around
scikit-learn LogisticRegression.

The model predicts the three decision-level outcomes:

    LONG_SUCCESS
    SHORT_SUCCESS
    NO_EDGE

The model does not make trading decisions. It only estimates outcome
probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ml.labeling.models import PredictionLabel


MODEL_CLASSES: tuple[str, ...] = (
    PredictionLabel.LONG_SUCCESS.value,
    PredictionLabel.SHORT_SUCCESS.value,
    PredictionLabel.NO_EDGE.value,
)


@dataclass(frozen=True)
class LogisticRegressionConfig:
    """
    Configuration for Logistic Regression v1.

    `C` controls inverse regularization strength.
    A smaller value means stronger regularization.

    `max_iter` provides enough iterations for convergence without
    changing the model family.
    """

    C: float = 1.0
    max_iter: int = 1000
    random_state: int = 42

    def __post_init__(self) -> None:
        """Validate model configuration."""

        if self.C <= 0:
            raise ValueError(
                "C must be greater than 0."
            )

        if self.max_iter <= 0:
            raise ValueError(
                "max_iter must be greater than 0."
            )


class LogisticOutcomeModel:
    """
    Thin auditable wrapper around sklearn LogisticRegression.

    The wrapper deliberately exposes probabilities rather than trading
    actions. Decision logic belongs to a later Phase 10 component.
    """

    def __init__(
        self,
        config: LogisticRegressionConfig | None = None,
    ) -> None:
        """Initialize an unfitted Logistic Regression model."""

        self.config = (
            config
            if config is not None
            else LogisticRegressionConfig()
        )

        self._model = LogisticRegression(
            C=self.config.C,
            max_iter=self.config.max_iter,
            random_state=self.config.random_state,
        )

        self._fitted = False
        self._feature_count: int | None = None

    @property
    def is_fitted(self) -> bool:
        """Return whether the model has been fitted."""

        return self._fitted

    @property
    def feature_count(self) -> int:
        """Return the number of features used by the fitted model."""

        if not self._fitted or self._feature_count is None:
            raise RuntimeError(
                "LogisticOutcomeModel has not been fitted."
            )

        return self._feature_count

    @property
    def classes(self) -> tuple[str, ...]:
        """Return the fitted class ordering."""

        if not self._fitted:
            raise RuntimeError(
                "LogisticOutcomeModel has not been fitted."
            )

        return tuple(
            str(value)
            for value in self._model.classes_
        )

    def fit(
        self,
        X: np.ndarray,
        y: pd.Series | np.ndarray,
    ) -> "LogisticOutcomeModel":
        """
        Fit Logistic Regression on already-preprocessed training data.

        Preprocessing must be fitted separately using training data only.
        """

        X_array = self._validate_X(X)

        y_array = self._validate_y(y)

        if len(X_array) != len(y_array):
            raise ValueError(
                "X and y must contain the same number of rows."
            )

        required_classes = set(MODEL_CLASSES)
        observed_classes = set(y_array)

        missing_classes = required_classes - observed_classes

        if missing_classes:
            raise ValueError(
                "Training data must contain all three Phase 9 prediction "
                "classes. Missing classes: "
                f"{sorted(missing_classes)}"
            )

        self._model.fit(
            X_array,
            y_array,
        )

        self._fitted = True
        self._feature_count = X_array.shape[1]

        return self

    def predict_proba(
        self,
        X: np.ndarray,
    ) -> pd.DataFrame:
        """
        Return class probabilities.

        Columns are always returned in the canonical STOCK BOT
        class order.
        """

        if not self._fitted:
            raise RuntimeError(
                "LogisticOutcomeModel must be fitted before prediction."
            )

        X_array = self._validate_X(X)

        probabilities = self._model.predict_proba(
            X_array
        )

        result = pd.DataFrame(
            0.0,
            index=range(len(X_array)),
            columns=list(MODEL_CLASSES),
        )

        for index, model_class in enumerate(
            self._model.classes_
        ):
            result[str(model_class)] = probabilities[:, index]

        result = result.loc[
            :,
            list(MODEL_CLASSES),
        ]

        if not np.isfinite(
            result.to_numpy(dtype=float)
        ).all():
            raise ValueError(
                "Model produced non-finite probabilities."
            )

        if not np.allclose(
            result.sum(axis=1).to_numpy(),
            1.0,
            atol=1e-8,
        ):
            raise ValueError(
                "Model probabilities must sum to 1."
            )

        return result

    @staticmethod
    def _validate_X(
        X: np.ndarray,
    ) -> np.ndarray:
        """Validate the preprocessed feature matrix."""

        if not isinstance(X, np.ndarray):
            raise TypeError(
                "X must be a numpy ndarray."
            )

        if X.ndim != 2:
            raise ValueError(
                "X must be a two-dimensional array."
            )

        if X.shape[0] == 0:
            raise ValueError(
                "X must contain at least one row."
            )

        if X.shape[1] == 0:
            raise ValueError(
                "X must contain at least one feature."
            )

        X_array = np.asarray(
            X,
            dtype=float,
        )

        if not np.isfinite(X_array).all():
            raise ValueError(
                "X must contain only finite values."
            )

        return X_array

    @staticmethod
    def _validate_y(
        y: pd.Series | np.ndarray,
    ) -> np.ndarray:
        """Validate the training target."""

        if isinstance(y, pd.Series):
            values = y.to_numpy()
        elif isinstance(y, np.ndarray):
            values = y
        else:
            raise TypeError(
                "y must be a pandas Series or numpy ndarray."
            )

        if values.ndim != 1:
            raise ValueError(
                "y must be one-dimensional."
            )

        if len(values) == 0:
            raise ValueError(
                "y must contain at least one value."
            )

        allowed = set(MODEL_CLASSES)
        observed = set(str(value) for value in values)

        invalid = observed - allowed

        if invalid:
            raise ValueError(
                "y contains invalid prediction labels: "
                f"{sorted(invalid)}"
            )

        return values.astype(str)
