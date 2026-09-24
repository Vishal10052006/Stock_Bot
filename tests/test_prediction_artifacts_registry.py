from pathlib import Path

import pandas as pd
import pytest

from ml.model_registry import ModelRegistryRecord
from ml.prediction.artifacts import load_prediction_artifact, save_prediction_artifact
from ml.prediction.contracts import PredictionProvenance
from ml.prediction.registry import PredictionModelRegistry


def _provenance() -> PredictionProvenance:
    return PredictionProvenance(
        model_version="phase9-logistic-test",
        model_family="logistic",
        dataset_version="dataset-test",
        feature_version="feature-test",
        target_version="target-test",
        code_version="code-test",
        calibration_version="isotonic-v1",
    )


def test_prediction_artifact_round_trip(tmp_path: Path) -> None:
    model = {"kind": "test", "values": [1, 2, 3]}
    manifest = save_prediction_artifact(
        tmp_path / "model.pkl",
        model=model,
        provenance=_provenance(),
        created_at="2026-09-23T00:00:00Z",
    )

    loaded, loaded_manifest = load_prediction_artifact(tmp_path / "model.pkl")
    assert loaded == model
    assert loaded_manifest.artifact_sha256 == manifest.artifact_sha256


def test_prediction_artifact_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "model.pkl"
    save_prediction_artifact(
        path,
        model={"kind": "test"},
        provenance=_provenance(),
        created_at="2026-09-23T00:00:00Z",
    )
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        load_prediction_artifact(path)


def test_registry_round_trip_and_status(tmp_path: Path) -> None:
    record = ModelRegistryRecord(
        model_version="phase9-logistic-test",
        model_family="logistic",
        feature_version="feature-test",
        dataset_version="dataset-test",
        code_version="code-test",
        training_period_start="2026-06-01",
        training_period_end="2026-08-01",
        validation_period_start="2026-08-02",
        validation_period_end="2026-08-15",
        test_period_start="2026-08-16",
        test_period_end="2026-08-31",
        hyperparameters={"C": 1.0},
        metrics={"log_loss": 1.0},
    )
    registry = PredictionModelRegistry(tmp_path / "registry.json")
    registry.register(record)
    assert registry.get(record.model_version) == record
    assert registry.list_versions() == (record.model_version,)

    registry.set_status(record.model_version, "CANDIDATE")
    assert registry.get(record.model_version).approval_status == "CANDIDATE"
