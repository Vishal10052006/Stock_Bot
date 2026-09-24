"""
Leakage-safe preprocessing pipeline for Phase 9.

Learned preprocessing statistics are fitted only on the supplied
training dataset. Validation and test data must only be transformed
using an already-fitted pipeline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    StandardScaler,
)

from .models import (
    BOOLEAN_FEATURES,
    NUMERIC_FEATURES,
    PreprocessingConfig,
    PreprocessingResult,
)


def _boolean_to_numeric(X: pd.DataFrame) -> pd.DataFrame:
    """Convert boolean feature columns to numeric values.

    Kept as a module-level callable so the fitted preprocessing pipeline
    remains serializable for candidate artifact identity and registry
    provenance. A local lambda would make an otherwise valid fitted
    pipeline unpicklable.
    """
    return X.astype(float)


class FeaturePreprocessor:
    """
    Leakage-safe transformer for STOCK BOT FeatureDataset v1.

    Numeric features:
        median imputation -> optional standardization

    Boolean features:
        most-frequent imputation -> numeric representation

    The sklearn pipeline learns statistics exclusively from data passed
    to `fit()`.
    """

    def __init__(
        self,
        config: PreprocessingConfig | None = None,
    ) -> None:
        """Initialize the preprocessing pipeline."""

        self.config = (
            config
            if config is not None
            else PreprocessingConfig()
        )

        numeric_steps = [
            (
                "imputer",
                SimpleImputer(
                    strategy=self.config.numeric_strategy,
                ),
            ),
        ]

        if self.config.scale_numeric:
            numeric_steps.append(
                (
                    "scaler",
                    StandardScaler(),
                )
            )

        numeric_pipeline = Pipeline(
            steps=numeric_steps
        )

        boolean_pipeline = Pipeline(
            steps=[
                (
                    "to_numeric",
                    FunctionTransformer(
                        _boolean_to_numeric,
                        feature_names_out="one-to-one",
                    ),
                ),
                (
                    "imputer",
                    SimpleImputer(
                        strategy=self.config.boolean_strategy,
                    ),
                ),
            ]
        )

        self._transformer = ColumnTransformer(
            transformers=[
                (
                    "numeric",
                    numeric_pipeline,
                    list(NUMERIC_FEATURES),
                ),
                (
                    "boolean",
                    boolean_pipeline,
                    list(BOOLEAN_FEATURES),
                ),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )

        self._fitted = False
        self._result: PreprocessingResult | None = None

    @property
    def transformer(self) -> ColumnTransformer:
        """Return the underlying sklearn transformer."""

        return self._transformer

    @property
    def result(self) -> PreprocessingResult:
        """Return metadata for the fitted transformer."""

        if not self._fitted or self._result is None:
            raise RuntimeError(
                "FeaturePreprocessor has not been fitted."
            )

        return self._result

    @property
    def is_fitted(self) -> bool:
        """Return whether the transformer has been fitted."""

        return self._fitted

    def fit(
        self,
        X_train: pd.DataFrame,
    ) -> "FeaturePreprocessor":
        """
        Fit preprocessing statistics using training data only.

        Parameters
        ----------
        X_train:
            Training feature matrix containing exactly the Phase 9
            feature columns.
        """

        self._validate_input(X_train)

        self._transformer.fit(X_train)

        self._fitted = True

        self._result = PreprocessingResult(
            feature_columns=tuple(
                X_train.columns
            ),
            numeric_columns=NUMERIC_FEATURES,
            boolean_columns=tuple(
                sorted(BOOLEAN_FEATURES)
            ),
            fitted_on_rows=len(X_train),
        )

        return self

    def transform(
        self,
        X: pd.DataFrame,
    ) -> np.ndarray:
        """
        Transform features using previously fitted training statistics.
        """

        if not self._fitted:
            raise RuntimeError(
                "FeaturePreprocessor must be fitted before transform()."
            )

        self._validate_input(X)

        transformed = self._transformer.transform(X)

        if not np.isfinite(
            np.asarray(transformed, dtype=float)
        ).all():
            raise ValueError(
                "Preprocessing produced non-finite values."
            )

        return np.asarray(
            transformed,
            dtype=float,
        )

    def fit_transform(
        self,
        X_train: pd.DataFrame,
    ) -> np.ndarray:
        """Fit on training data and transform that same training data."""

        self.fit(X_train)
        return self.transform(X_train)

    def get_feature_names_out(self) -> np.ndarray:
        """Return transformed feature names."""

        if not self._fitted:
            raise RuntimeError(
                "FeaturePreprocessor must be fitted first."
            )

        return self._transformer.get_feature_names_out()

    @staticmethod
    def _validate_input(
        X: pd.DataFrame,
    ) -> None:
        """Validate the feature matrix before transformation."""

        if not isinstance(X, pd.DataFrame):
            raise TypeError(
                "X must be a pandas DataFrame."
            )

        if X.empty:
            raise ValueError(
                "X must not be empty."
            )

        expected = (
            *NUMERIC_FEATURES,
            *sorted(BOOLEAN_FEATURES),
        )

        actual = tuple(X.columns)

        if set(actual) != set(expected):
            missing = [
                column
                for column in expected
                if column not in X.columns
            ]

            unexpected = [
                column
                for column in X.columns
                if column not in expected
            ]

            raise ValueError(
                "Invalid preprocessing feature schema; "
                f"missing={missing}, "
                f"unexpected={unexpected}"
            )
