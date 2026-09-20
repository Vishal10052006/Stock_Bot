"""Tests for AB-25 AnalysisContext -> Phase 9 prediction integration."""
from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from ml.integration.analysis_prediction import predict_from_analysis
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from ml.preprocessing.models import NUMERIC_FEATURES, BOOLEAN_FEATURES


def _training_frame(rows: int = 12) -> tuple[pd.DataFrame, pd.Series]:
    """Construct a small causal-format training matrix for adapter testing."""
    data: dict[str, list[object]] = {}
    for index, column in enumerate(NUMERIC_FEATURES):
        data[column] = [
            float(index + row + 1) / 100.0
            for row in range(rows)
        ]
    for index, column in enumerate(sorted(BOOLEAN_FEATURES)):
        data[column] = [
            bool((index + row) % 2)
            for row in range(rows)
        ]

    labels = pd.Series(
        [
            "LONG_SUCCESS",
            "SHORT_SUCCESS",
            "NO_EDGE",
        ]
        * (rows // 3)
        + ["LONG_SUCCESS"] * (rows % 3),
        name="label",
    )

    return pd.DataFrame(data), labels


def test_ab25_analysis_context_produces_phase9_probabilities() -> None:
    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    X_transformed = preprocessor.fit_transform(X_train)

    model = LogisticOutcomeModel()
    model.fit(X_transformed, y_train)

    features = {
        column: (
            True if column in BOOLEAN_FEATURES else float(X_train.iloc[-1][column])
        )
        for column in X_train.columns
    }

    analysis = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="RELIANCE",
            features=features,
            data_version="market-test-v1",
            feature_version="v1.0",
        )
    )

    prediction = predict_from_analysis(
        analysis,
        model=model,
        preprocessor=preprocessor,
    )

    assert prediction.symbol == "RELIANCE"
    assert prediction.predicted_class in {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }
    assert np.isfinite(prediction.probabilities.to_numpy()).all()
    assert np.isclose(
        prediction.probabilities.iloc[0].sum(),
        1.0,
        atol=1e-8,
    )


def test_ab25_does_not_use_analysis_direction_as_prediction() -> None:
    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    X_transformed = preprocessor.fit_transform(X_train)

    model = LogisticOutcomeModel()
    model.fit(X_transformed, y_train)

    feature_values = {
        column: (
            True if column in BOOLEAN_FEATURES else float(X_train.iloc[0][column])
        )
        for column in X_train.columns
    }

    analysis = AnalysisEngine().analyze(
        AnalysisInput(
            timestamp=pd.Timestamp("2026-09-20 10:25:00+05:30"),
            symbol="TCS",
            features=feature_values,
        )
    )

    prediction = predict_from_analysis(
        analysis,
        model=model,
        preprocessor=preprocessor,
    )

    # The predicted class comes from model probabilities, not the analysis label.
    assert prediction.predicted_class == str(
        prediction.probabilities.iloc[0].idxmax()
    )
