"""Versioned model artifact persistence for the Prediction Bot.

Artifacts are research/runtime objects, not trade authorization.  The
manifest is JSON and the learned payload is a pickle byte stream.  Loading
must only be performed on artifacts from a trusted source because pickle is
not a safe interchange format for untrusted input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import pickle
from typing import Any

from ml.prediction.contracts import PredictionProvenance
from ml.models.calibration import IsotonicProbabilityCalibrator
from ml.models.logistic import LogisticOutcomeModel
from ml.preprocessing.pipeline import FeaturePreprocessor


@dataclass(frozen=True, slots=True)
class PredictionArtifactManifest:
    """Immutable manifest describing a serialized prediction model."""

    artifact_version: str
    model_version: str
    provenance: PredictionProvenance
    artifact_sha256: str
    created_at: str

    def __post_init__(self) -> None:
        if not self.artifact_version.strip():
            raise ValueError("artifact_version must not be empty")
        if len(self.artifact_sha256) != 64:
            raise ValueError("artifact_sha256 must be a SHA-256 hex digest")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def save_prediction_artifact(
    path: str | Path,
    *,
    model: Any,
    provenance: PredictionProvenance,
    created_at: str,
    artifact_version: str = "prediction-artifact-v1",
) -> PredictionArtifactManifest:
    """Persist a trusted model object and a hash-bound JSON manifest."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    digest = _sha256(payload)

    destination.write_bytes(payload)

    manifest = PredictionArtifactManifest(
        artifact_version=artifact_version,
        model_version=provenance.model_version,
        provenance=provenance,
        artifact_sha256=digest,
        created_at=created_at,
    )
    destination.with_suffix(destination.suffix + ".json").write_text(
        json.dumps(asdict(manifest), sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )
    return manifest


def load_prediction_artifact(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[Any, PredictionArtifactManifest]:
    """Load a trusted artifact after verifying its manifest and byte hash."""
    source = Path(path)
    manifest_path = source.with_suffix(source.suffix + ".json")
    if not source.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("artifact and manifest must both exist")

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance_data = manifest_data["provenance"]
    provenance = PredictionProvenance(**provenance_data)
    manifest = PredictionArtifactManifest(
        artifact_version=str(manifest_data["artifact_version"]),
        model_version=str(manifest_data["model_version"]),
        provenance=provenance,
        artifact_sha256=str(manifest_data["artifact_sha256"]),
        created_at=str(manifest_data["created_at"]),
    )

    payload = source.read_bytes()
    digest = _sha256(payload)
    if digest != manifest.artifact_sha256:
        raise ValueError("artifact SHA-256 does not match its manifest")
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("artifact SHA-256 does not match expected_sha256")

    model = pickle.loads(payload)
    return model, manifest

def load_phase9_logistic_bundle(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[LogisticOutcomeModel, FeaturePreprocessor, IsotonicProbabilityCalibrator, PredictionArtifactManifest]:
    """Load a hash-verified Phase-9 Logistic calibrated inference bundle."""
    model, manifest = load_prediction_artifact(
        path,
        expected_sha256=expected_sha256,
    )
    if not isinstance(model, dict):
        raise TypeError("Phase-9 artifact payload must be a mapping")
    fitted_model = model.get("model")
    fitted_preprocessor = model.get("preprocessor")
    fitted_calibrator = model.get("calibrator")
    if not isinstance(fitted_model, LogisticOutcomeModel):
        raise TypeError("Phase-9 artifact model must be LogisticOutcomeModel")
    if not isinstance(fitted_preprocessor, FeaturePreprocessor):
        raise TypeError("Phase-9 artifact preprocessor must be FeaturePreprocessor")
    if not isinstance(fitted_calibrator, IsotonicProbabilityCalibrator):
        raise TypeError("Phase-9 artifact calibrator must be IsotonicProbabilityCalibrator")
    if not fitted_model.is_fitted or not fitted_preprocessor.is_fitted or not fitted_calibrator.is_fitted:
        raise ValueError("Phase-9 model, preprocessor, and calibrator must all be fitted")
    if fitted_model.feature_count != len(fitted_preprocessor.get_feature_names_out()):
        raise ValueError("Phase-9 model/preprocessor feature counts do not match")
    return fitted_model, fitted_preprocessor, fitted_calibrator, manifest
