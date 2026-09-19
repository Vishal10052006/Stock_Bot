"""Leakage-safe probability calibration for STOCK BOT Phase 9.

Calibration is fitted on a chronological holdout carved from the training
partition. The final validation partition remains untouched until evaluation.

A one-vs-rest isotonic calibrator is used because it is non-parametric and
keeps the implementation independent of broker/trading decisions.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 9, probability calibration requirement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .logistic import MODEL_CLASSES


class IsotonicProbabilityCalibrator:
    """Calibrate multiclass probabilities using one-vs-rest isotonic models."""

    def __init__(self) -> None:
        """Initialize an unfitted probability calibrator."""
        self._models = {
            label: IsotonicRegression(
                y_min=0.0,
                y_max=1.0,
                out_of_bounds="clip",
            )
            for label in MODEL_CLASSES
        }
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        """Return whether calibration models have been fitted."""
        return self._fitted

    def fit(
        self,
        probabilities: pd.DataFrame,
        y_true: pd.Series | np.ndarray,
    ) -> "IsotonicProbabilityCalibrator":
        """Fit calibration maps on a chronological calibration partition."""
        values = self._validate_probabilities(probabilities)
        labels = self._validate_labels(y_true)

        if len(values) != len(labels):
            raise ValueError(
                "probabilities and y_true must contain the same number of rows."
            )

        for label in MODEL_CLASSES:
            target = (labels == label).astype(float)

            # Isotonic regression needs both positive and negative examples.
            if np.unique(target).size < 2:
                raise ValueError(
                    "Calibration data must contain both positive and negative "
                    f"examples for {label}."
                )

            self._models[label].fit(values[:, MODEL_CLASSES.index(label)], target)

        self._fitted = True
        return self

    def transform(self, probabilities: pd.DataFrame) -> pd.DataFrame:
        """Calibrate probabilities and renormalize each row to sum to one."""
        if not self._fitted:
            raise RuntimeError(
                "IsotonicProbabilityCalibrator must be fitted before transform()."
            )

        values = self._validate_probabilities(probabilities)
        calibrated = np.column_stack(
            [
                self._models[label].predict(values[:, index])
                for index, label in enumerate(MODEL_CLASSES)
            ]
        )

        calibrated = np.clip(calibrated, 0.0, 1.0)
        totals = calibrated.sum(axis=1)

        # A row with zero calibrated mass is not meaningful; fall back to the
        # original normalized probabilities rather than inventing a class.
        zero_mask = totals <= 1e-12
        calibrated[~zero_mask] /= totals[~zero_mask, None]
        calibrated[zero_mask] = values[zero_mask]

        result = pd.DataFrame(
            calibrated,
            columns=list(MODEL_CLASSES),
        )

        if not np.isfinite(result.to_numpy(dtype=float)).all():
            raise ValueError("Calibrator produced non-finite probabilities.")

        return result

    @staticmethod
    def _validate_probabilities(probabilities: pd.DataFrame) -> np.ndarray:
        """Validate canonical probability input."""
        if not isinstance(probabilities, pd.DataFrame):
            raise TypeError("probabilities must be a pandas DataFrame.")
        if list(probabilities.columns) != list(MODEL_CLASSES):
            raise ValueError(
                "probabilities must use the canonical Phase 9 class order."
            )

        values = probabilities.to_numpy(dtype=float)

        if values.ndim != 2 or len(values) == 0:
            raise ValueError("probabilities must be a non-empty 2D matrix.")
        if not np.isfinite(values).all():
            raise ValueError("probabilities must contain only finite values.")
        if (values < 0.0).any() or (values > 1.0).any():
            raise ValueError("probabilities must lie in [0, 1].")
        if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
            raise ValueError("probability rows must sum to 1.")

        return values

    @staticmethod
    def _validate_labels(
        y_true: pd.Series | np.ndarray,
    ) -> np.ndarray:
        """Validate canonical outcome labels."""
        if isinstance(y_true, pd.Series):
            values = y_true.to_numpy()
        elif isinstance(y_true, np.ndarray):
            values = y_true
        else:
            raise TypeError("y_true must be a pandas Series or numpy ndarray.")

        if values.ndim != 1 or len(values) == 0:
            raise ValueError("y_true must be a non-empty one-dimensional array.")

        values = values.astype(str)
        invalid = set(values) - set(MODEL_CLASSES)

        if invalid:
            raise ValueError(
                f"y_true contains invalid prediction labels: {sorted(invalid)}"
            )

        return values
