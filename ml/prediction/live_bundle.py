"""Trusted model bundle used by the live prediction runtime.

The bundle contains the already-fitted model and preprocessor required for
inference. Loading is hash-verified and never trains or promotes a model.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ml.models.logistic import LogisticOutcomeModel
from ml.prediction.artifacts import (
    PredictionArtifactManifest,
    load_prediction_artifact,
    save_prediction_artifact,
)
from ml.preprocessing.pipeline import FeaturePreprocessor
from ml.prediction.contracts import PredictionProvenance


@dataclass(frozen=True, slots=True)
class LivePredictionBundle:
    """Fitted inference components plus immutable provenance."""

    model: LogisticOutcomeModel
    preprocessor: FeaturePreprocessor
    provenance: PredictionProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.model, LogisticOutcomeModel):
            raise TypeError("model must be LogisticOutcomeModel")
        if not isinstance(self.preprocessor, FeaturePreprocessor):
            raise TypeError("preprocessor must be FeaturePreprocessor")
        if not isinstance(self.provenance, PredictionProvenance):
            raise TypeError("provenance must be PredictionProvenance")
        if not self.model.is_fitted:
            raise ValueError("model must be fitted")
        if not self.preprocessor.is_fitted:
            raise ValueError("preprocessor must be fitted")
        if self.model.feature_count != len(self.preprocessor.get_feature_names_out()):
            raise ValueError("model/preprocessor feature counts do not match")


def save_live_prediction_bundle(
    path: str | Path,
    *,
    model: LogisticOutcomeModel,
    preprocessor: FeaturePreprocessor,
    provenance: PredictionProvenance,
    created_at: str,
) -> PredictionArtifactManifest:
    """Persist one trusted fitted model bundle with a SHA-256 manifest."""
    bundle = LivePredictionBundle(
        model=model,
        preprocessor=preprocessor,
        provenance=provenance,
    )
    return save_prediction_artifact(
        path,
        model=bundle,
        provenance=provenance,
        created_at=created_at,
    )


def load_live_prediction_bundle(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[LivePredictionBundle, PredictionArtifactManifest]:
    """Load and verify one trusted live inference bundle."""
    artifact, manifest = load_prediction_artifact(
        path,
        expected_sha256=expected_sha256,
    )
    if not isinstance(artifact, LivePredictionBundle):
        raise TypeError("prediction artifact is not a LivePredictionBundle")
    return artifact, manifest


__all__ = [
    "LivePredictionBundle",
    "load_live_prediction_bundle",
    "save_live_prediction_bundle",
]
