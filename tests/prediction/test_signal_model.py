"""Tests for the Phase 9 SignalModel v1.0 prediction contract."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.datasets import TrainingDataset
from ml.models import IsotonicProbabilityCalibrator, LogisticOutcomeModel
from ml.prediction import SignalModel
from market.features.builder import FEATURE_COLUMNS
from ml.preprocessing import BOOLEAN_FEATURES, NUMERIC_FEATURES


def make_components():
    """Build deterministic fitted Phase 9 components."""
    rows = 120
    rng = np.random.default_rng(42)

    features = pd.DataFrame(
        {
            column: rng.normal(size=rows)
            for column in NUMERIC_FEATURES
        }
    )

    for column in BOOLEAN_FEATURES:
        features[column] = pd.Series(
            rng.choice([True, False], size=rows),
            dtype="boolean",
        )

    labels = pd.Series(
        ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"] * (rows // 3)
    )

    from ml.preprocessing import FeaturePreprocessor

    preprocessor = FeaturePreprocessor()
    X = preprocessor.fit_transform(features)

    model = LogisticOutcomeModel()
    model.fit(X, labels)

    raw = model.predict_proba(X)
    calibrator = IsotonicProbabilityCalibrator()
    calibrator.fit(raw, labels)

    features = features.loc[:, list(FEATURE_COLUMNS)]
    return preprocessor, model, calibrator, features


def test_signal_model_returns_probability_contract() -> None:
    """SignalModel exposes probabilities and model version only."""
    preprocessor, model, calibrator, features = make_components()

    signal_model = SignalModel(
        preprocessor=preprocessor,
        model=model,
        calibrator=calibrator,
    )

    identifiers = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01",
                periods=5,
                freq="5min",
                tz="Asia/Kolkata",
            ),
            "symbol": ["TEST"] * 5,
        }
    )

    result = signal_model.predict(
        features.iloc[:5].reset_index(drop=True),
        identifiers=identifiers,
    )

    assert list(result.columns) == [
        "timestamp",
        "symbol",
        "long_probability",
        "short_probability",
        "no_edge_probability",
        "model_version",
    ]
    assert result["model_version"].eq("1.0").all()

    probabilities = result[
        [
            "long_probability",
            "short_probability",
            "no_edge_probability",
        ]
    ].to_numpy()

    assert np.isfinite(probabilities).all()
    assert np.allclose(probabilities.sum(axis=1), 1.0)
