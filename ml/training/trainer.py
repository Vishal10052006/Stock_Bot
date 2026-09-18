"""Phase 9 training orchestration.

The chronology is:
    temporal split
        -> chronological calibration holdout inside train
        -> fit preprocessing on classifier-fit rows only
        -> fit Logistic Regression
        -> fit isotonic calibration on later training rows
        -> predict calibrated validation probabilities

The external test partition remains untouched.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 9, First ML Model.
"""

from __future__ import annotations

import pandas as pd

from ml.datasets.models import TrainingDataset
from ml.datasets.splitting import temporal_split
from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor

from .models import TrainingConfig, TrainingResult


def _split_training_for_calibration(
    dataset: TrainingDataset,
    calibration_ratio: float,
) -> tuple[TrainingDataset, TrainingDataset]:
    """Reserve the latest training observations for calibration.

    The split uses global decision timestamps so all symbols share the same
    temporal boundary. No random sampling is permitted.
    """
    timestamps = (
        dataset.data["timestamp"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    if len(timestamps) < 4:
        raise ValueError(
            "Calibration split requires at least four unique timestamps."
        )

    calibration_count = max(
        1,
        int(len(timestamps) * calibration_ratio),
    )
    calibration_index = len(timestamps) - calibration_count

    if calibration_index <= 0:
        raise ValueError("Calibration split left no classifier-training data.")

    boundary = timestamps.iloc[calibration_index - 1]

    fit_data = dataset.data.loc[
        dataset.data["timestamp"] <= boundary
    ].copy()
    calibration_data = dataset.data.loc[
        dataset.data["timestamp"] > boundary
    ].copy()

    if fit_data.empty or calibration_data.empty:
        raise ValueError("Calibration split produced an empty partition.")

    feature_columns = dataset.feature_columns

    return (
        TrainingDataset(
            data=fit_data.reset_index(drop=True),
            feature_columns=feature_columns,
        ),
        TrainingDataset(
            data=calibration_data.reset_index(drop=True),
            feature_columns=feature_columns,
        ),
    )


def train_baseline(
    dataset: TrainingDataset,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    """Train the Phase 9 calibrated Logistic Regression baseline."""
    if config is None:
        config = TrainingConfig()

    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset.")

    split = temporal_split(dataset, config=config.split)

    classifier_train, calibration_train = _split_training_for_calibration(
        split.train,
        config.calibration_ratio,
    )

    preprocessor = FeaturePreprocessor(config=config.preprocessing)

    X_train = preprocessor.fit_transform(classifier_train.X)

    model = LogisticOutcomeModel(config=config.model)
    model.fit(X_train, classifier_train.y)

    # Calibration data is later than classifier-training data, but still
    # earlier than the untouched validation partition.
    X_calibration = preprocessor.transform(calibration_train.X)
    raw_calibration_probabilities = model.predict_proba(X_calibration)

    calibrator = IsotonicProbabilityCalibrator()
    calibrator.fit(
        raw_calibration_probabilities,
        calibration_train.y,
    )

    X_validation = preprocessor.transform(split.validation.X)
    raw_validation_probabilities = model.predict_proba(X_validation)
    validation_probabilities = calibrator.transform(
        raw_validation_probabilities,
    )

    return TrainingResult(
        train_rows=len(classifier_train.data),
        calibration_rows=len(calibration_train.data),
        validation_rows=len(split.validation.data),
        test_rows=len(split.test.data),
        train_end=split.train_end,
        validation_start=split.validation_start,
        validation_end=split.validation_end,
        test_start=split.test_start,
        validation_probabilities=validation_probabilities,
        preprocessor=preprocessor,
        model=model,
        calibrator=calibrator,
    )
