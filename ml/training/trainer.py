"""
Phase 9 training orchestration.

This module connects the existing temporal splitter, preprocessing
pipeline, and Logistic Regression model.

The test partition is deliberately not transformed or evaluated here.
"""

from __future__ import annotations

from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import temporal_split
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor

from .models import TrainingConfig, TrainingResult


def train_baseline(
    dataset: TrainingDataset,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    """
    Train the Phase 9 Logistic Regression baseline.

    Parameters
    ----------
    dataset:
        Validated supervised TrainingDataset containing causal features
        and decision-level labels.

    config:
        Optional training configuration.

    Returns
    -------
    TrainingResult
        Fitted preprocessing/model objects and validation probabilities.

    Notes
    -----
    The temporal split is performed before any learned preprocessing.
    The preprocessor is fitted exclusively on the training partition.
    The Logistic Regression model is fitted exclusively on the
    preprocessed training partition.

    The test partition is intentionally left untouched.
    """

    if config is None:
        config = TrainingConfig()

    if not isinstance(dataset, TrainingDataset):
        raise TypeError(
            "dataset must be a TrainingDataset."
        )

    split = temporal_split(
        dataset,
        config=config.split,
    )

    preprocessor = FeaturePreprocessor(
        config=config.preprocessing,
    )

    X_train = preprocessor.fit_transform(
        split.train.X
    )

    y_train = split.train.y

    model = LogisticOutcomeModel(
        config=config.model,
    )

    model.fit(
        X_train,
        y_train,
    )

    X_validation = preprocessor.transform(
        split.validation.X
    )

    validation_probabilities = model.predict_proba(
        X_validation
    )

    return TrainingResult(
        train_rows=len(split.train.data),
        validation_rows=len(split.validation.data),
        test_rows=len(split.test.data),
        train_end=split.train_end,
        validation_start=split.validation_start,
        validation_end=split.validation_end,
        test_start=split.test_start,
        validation_probabilities=validation_probabilities,
        preprocessor=preprocessor,
        model=model,
    )
