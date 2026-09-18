"""Core models for Phase 9 model training.

Training is separated from model definition and preprocessing. Learned
components are fitted only on chronological training data.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 9, First ML Model.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml.datasets.splitting import TemporalSplitConfig
from ml.models.logistic import LogisticRegressionConfig
from ml.preprocessing.models import PreprocessingConfig


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration for the Phase 9 baseline training run."""

    split: TemporalSplitConfig = TemporalSplitConfig()
    preprocessing: PreprocessingConfig = PreprocessingConfig()
    model: LogisticRegressionConfig = LogisticRegressionConfig()

    # The final portion of the chronological training partition is reserved
    # for probability calibration and is never used to fit the base classifier.
    calibration_ratio: float = 0.15

    def __post_init__(self) -> None:
        """Validate training configuration."""
        if not isinstance(self.split, TemporalSplitConfig):
            raise TypeError("split must be a TemporalSplitConfig.")
        if not isinstance(self.preprocessing, PreprocessingConfig):
            raise TypeError("preprocessing must be a PreprocessingConfig.")
        if not isinstance(self.model, LogisticRegressionConfig):
            raise TypeError("model must be a LogisticRegressionConfig.")
        if not 0.0 < self.calibration_ratio < 0.5:
            raise ValueError("calibration_ratio must be between 0 and 0.5.")


@dataclass(frozen=True)
class TrainingResult:
    """Result of a Phase 9 training run."""

    train_rows: int
    calibration_rows: int
    validation_rows: int
    test_rows: int

    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp

    validation_probabilities: pd.DataFrame

    preprocessor: object
    model: object
    calibrator: object

    @property
    def validation_predictions(self) -> pd.Series:
        """Return the highest-probability validation class.

        This is a model prediction only. It is not a trading decision.
        """
        return self.validation_probabilities.idxmax(axis=1)

    def __post_init__(self) -> None:
        """Validate the training result contract."""
        if self.train_rows <= 0:
            raise ValueError("train_rows must be greater than 0.")
        if self.calibration_rows <= 0:
            raise ValueError("calibration_rows must be greater than 0.")
        if self.validation_rows <= 0:
            raise ValueError("validation_rows must be greater than 0.")
        if self.test_rows <= 0:
            raise ValueError("test_rows must be greater than 0.")

        if not isinstance(self.validation_probabilities, pd.DataFrame):
            raise TypeError("validation_probabilities must be a DataFrame.")

        if len(self.validation_probabilities) != self.validation_rows:
            raise ValueError(
                "validation probability row count must match validation_rows."
            )

        expected_columns = [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        ]

        if list(self.validation_probabilities.columns) != expected_columns:
            raise ValueError(
                "validation_probabilities must use the canonical "
                "three-class column order."
            )

        if not self.validation_probabilities.apply(
            lambda column: column.between(0.0, 1.0).all()
        ).all():
            raise ValueError("validation probabilities must lie in [0, 1].")

        if not (
            self.validation_probabilities.sum(axis=1)
            .sub(1.0)
            .abs()
            .le(1e-8)
            .all()
        ):
            raise ValueError("validation probability rows must sum to 1.")
