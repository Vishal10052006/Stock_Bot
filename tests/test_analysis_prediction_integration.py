"""Tests for AB-25 AnalysisContext -> Phase 9 prediction integration.

Conflict-resolution note: the integration fixture follows the frozen FeatureDataset schema.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from intelligence.analysis.contracts import AnalysisInput
from intelligence.analysis.engine import AnalysisEngine
from ml.integration.analysis_prediction import predict_from_analysis
from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor
from ml.preprocessing.models import NUMERIC_FEATURES, BOOLEAN_FEATURES
from monitoring.runtime import MonitoringRuntime
from market.features.validation import EXPECTED_COLUMNS, BOOLEAN_FEATURES as FEATURE_BOOLEAN_COLUMNS


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


def test_analysis_integration_emits_monitoring_telemetry() -> None:
    from intelligence.analysis.integration import build_analysis_context

    X_train, _ = _training_frame()
    rows = len(X_train)
    feature_values: dict[str, object] = {}
    for index, column in enumerate(EXPECTED_COLUMNS):
        if column == "timestamp":
            feature_values[column] = pd.date_range(
                "2026-09-20",
                periods=rows,
                tz="UTC",
            )
        elif column == "symbol":
            feature_values[column] = ["RELIANCE"] * rows
        elif column in FEATURE_BOOLEAN_COLUMNS:
            feature_values[column] = [
                bool((index + row) % 2) for row in range(rows)
            ]
        else:
            feature_values[column] = [
                float(index + row + 1) / 100.0 for row in range(rows)
            ]
    features = pd.DataFrame(feature_values, columns=EXPECTED_COLUMNS)
    runtime = MonitoringRuntime()
    context = build_analysis_context(
        features,
        monitoring=runtime,
        data_version="test-data",
        feature_version="test-features",
    )
    dashboard = runtime.dashboard()
    assert context.symbol == "RELIANCE"
    assert "analysis.completeness" in dashboard["metrics"]
    assert any(item["component"] == "analysis_bot" for item in dashboard["health"])


def test_ab25_applies_calibrated_probabilities_when_calibrator_is_supplied() -> None:
    X_train, y_train = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(X_train)

    model = LogisticOutcomeModel()
    model.fit(transformed, y_train)

    calibrator = IsotonicProbabilityCalibrator()
    raw = model.predict_proba(transformed)
    calibrator.fit(raw, y_train)

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
        calibrator=calibrator,
        target_version="phase7-decision-label-v1",
        calibration_version="isotonic-v1",
    )

    expected = calibrator.transform(
        model.predict_proba(
            preprocessor.transform(pd.DataFrame([dict(analysis.feature_vector)]))
        )
    )

    assert prediction.calibration_version == "isotonic-v1"
    assert prediction.target_version == "phase7-decision-label-v1"
    assert np.allclose(
        prediction.probabilities.to_numpy(),
        expected.to_numpy(),
        atol=1e-12,
    )
