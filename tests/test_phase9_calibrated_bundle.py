"""Regression tests for the Phase-9 calibrated inference artifact."""

from __future__ import annotations

import pandas as pd

from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import LogisticOutcomeModel
from ml.prediction.artifacts import (
    load_phase9_logistic_bundle,
    save_prediction_artifact,
)
from ml.prediction.contracts import PredictionProvenance
from ml.preprocessing.pipeline import FeaturePreprocessor
from ml.preprocessing.models import BOOLEAN_FEATURES, NUMERIC_FEATURES


def _training_frame(rows: int = 12) -> tuple[pd.DataFrame, pd.Series]:
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
        ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"] * (rows // 3)
        + ["LONG_SUCCESS"] * (rows % 3),
        name="label",
    )
    return pd.DataFrame(data), labels


def test_phase9_logistic_bundle_round_trips_calibrator(tmp_path) -> None:
    features, labels = _training_frame()
    preprocessor = FeaturePreprocessor()
    transformed = preprocessor.fit_transform(features)

    model = LogisticOutcomeModel()
    model.fit(transformed, labels)

    calibrator = IsotonicProbabilityCalibrator()
    calibrator.fit(model.predict_proba(transformed), labels)

    provenance = PredictionProvenance(
        model_version="phase9-logistic-test",
        model_family="logistic",
        dataset_version="dataset-test",
        feature_version="v1.0",
        target_version="phase7-decision-label-v1",
        code_version="test",
        calibration_version="isotonic-v1",
    )

    path = tmp_path / "phase9.pkl"
    manifest = save_prediction_artifact(
        path,
        model={
            "model": model,
            "preprocessor": preprocessor,
            "calibrator": calibrator,
        },
        provenance=provenance,
        created_at="2026-10-02T00:00:00Z",
    )

    loaded_model, loaded_preprocessor, loaded_calibrator, loaded_manifest = (
        load_phase9_logistic_bundle(
            path,
            expected_sha256=manifest.artifact_sha256,
        )
    )

    assert loaded_model.is_fitted
    assert loaded_preprocessor.is_fitted
    assert loaded_calibrator.is_fitted
    assert loaded_manifest.provenance.calibration_version == "isotonic-v1"
