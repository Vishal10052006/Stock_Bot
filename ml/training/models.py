"""
Core models for Phase 9 model training.

Training is deliberately separated from model definition and
preprocessing. The trainer fits learned components only on the
chronological training partition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from ml.datasets.splitting import TemporalSplitConfig
from ml.models.logistic import LogisticRegressionConfig
from ml.preprocessing.models import PreprocessingConfig


@dataclass(frozen=True)
class TrainingConfig:
    """
    Configuration for the Phase 9 baseline training run.

    The temporal split configuration is kept explicit so that the
    training run is reproducible and auditable.
    """

    split: TemporalSplitConfig = TemporalSplitConfig()
    preprocessing: PreprocessingConfig = PreprocessingConfig()
    model: LogisticRegressionConfig = LogisticRegressionConfig()

    def __post_init__(self) -> None:
        """Validate training configuration."""

        if not isinstance(
            self.split,
            TemporalSplitConfig,
        ):
            raise TypeError(
                "split must be a TemporalSplitConfig."
            )

        if not isinstance(
            self.preprocessing,
            PreprocessingConfig,
        ):
            raise TypeError(
                "preprocessing must be a PreprocessingConfig."
            )

        if not isinstance(
            self.model,
            LogisticRegressionConfig,
        ):
            raise TypeError(
                "model must be a LogisticRegressionConfig."
            )


@dataclass(frozen=True)
class TrainingResult:
    """
    Result of a Phase 9 training run.

    The result contains the fitted training components and validation
    predictions. Test data is intentionally not evaluated here.
    """

    train_rows: int
    validation_rows: int
    test_rows: int

    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp

    validation_probabilities: pd.DataFrame

    preprocessor: object
    model: object

    @property
    def validation_predictions(self) -> pd.Series:
        """
        Return the highest-probability validation class.

        This is a model prediction only. It is NOT a trading decision.
        """

        return self.validation_probabilities.idxmax(
            axis=1
        )

    def __post_init__(self) -> None:
        """Validate the training result contract."""

        if self.train_rows <= 0:
            raise ValueError(
                "train_rows must be greater than 0."
            )

        if self.validation_rows <= 0:
            raise ValueError(
                "validation_rows must be greater than 0."
            )

        if self.test_rows <= 0:
            raise ValueError(
                "test_rows must be greater than 0."
            )

        if not isinstance(
            self.validation_probabilities,
            pd.DataFrame,
        ):
            raise TypeError(
                "validation_probabilities must be a DataFrame."
            )

        if len(self.validation_probabilities) != (
            self.validation_rows
        ):
            raise ValueError(
                "validation probability row count must match "
                "validation_rows."
            )

        expected_columns = [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        ]

        if list(
            self.validation_probabilities.columns
        ) != expected_columns:
            raise ValueError(
                "validation_probabilities must use the canonical "
                "three-class column order."
            )
