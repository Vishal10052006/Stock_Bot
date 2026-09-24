"""Controlled retraining adapter for the existing Phase-9 trainer.

This module deliberately returns a training result and provenance metadata.
It does not choose a model, mutate a production model, or promote anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import pickle
from typing import Any, Callable

from ml.datasets.models import TrainingDataset
from ml.training.models import TrainingConfig, TrainingResult
from ml.training.trainer import train_baseline, train_random_forest

from .contracts import DatasetVersion, ExperimentSpec
from .dataset import dataframe_fingerprint


@dataclass(frozen=True, slots=True)
class RetrainingResult:
    """Immutable candidate-training output."""

    model_family: str
    result: TrainingResult
    dataset_version: str
    experiment_fingerprint: str
    artifact_fingerprint: str
    status: str = "CANDIDATE"

    def __post_init__(self) -> None:
        if not self.model_family.strip():
            raise ValueError("model_family must not be empty")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must not be empty")
        if len(self.experiment_fingerprint) != 64:
            raise ValueError("experiment_fingerprint must be SHA-256")
        if len(self.artifact_fingerprint) != 64:
            raise ValueError("artifact_fingerprint must be SHA-256")
        if self.status != "CANDIDATE":
            raise ValueError("retraining output must remain a CANDIDATE")


def retrain_candidate(
    dataset: TrainingDataset,
    *,
    dataset_version: DatasetVersion,
    experiment: ExperimentSpec,
    trainer: str = "logistic_regression",
    config: TrainingConfig | None = None,
    artifact_serializer: Callable[[Any], bytes] | None = None,
) -> RetrainingResult:
    """Run the existing chronological Phase-9 trainer for a candidate.

    The trainer selection is explicit. No automatic production replacement
    happens here. The supplied TrainingDataset must also match the immutable
    source fingerprint recorded by DatasetVersion.
    """
    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")
    if not isinstance(dataset_version, DatasetVersion):
        raise TypeError("dataset_version must be a DatasetVersion")
    if not isinstance(experiment, ExperimentSpec):
        raise TypeError("experiment must be an ExperimentSpec")
    if experiment.dataset_version != dataset_version.dataset_version:
        raise ValueError("experiment and dataset versions do not match")

    actual_fingerprint = dataframe_fingerprint(dataset.data)
    if actual_fingerprint not in dataset_version.source_fingerprints:
        raise ValueError(
            "training dataset does not match DatasetVersion source fingerprint"
        )

    config = config or TrainingConfig()

    if trainer == "logistic_regression":
        result = train_baseline(dataset, config)
    elif trainer == "random_forest":
        result = train_random_forest(dataset, config)
    else:
        raise ValueError(f"unsupported candidate trainer: {trainer}")

    if artifact_serializer is None:
        serialized = _default_artifact_serializer(result)
    else:
        serialized = artifact_serializer(result.model)

    if not isinstance(serialized, (bytes, bytearray)):
        raise TypeError("artifact serializer must return bytes")

    artifact_fingerprint = hashlib.sha256(bytes(serialized)).hexdigest()

    return RetrainingResult(
        model_family=trainer,
        result=result,
        dataset_version=dataset_version.dataset_version,
        experiment_fingerprint=experiment.fingerprint,
        artifact_fingerprint=artifact_fingerprint,
    )


def _default_artifact_serializer(result: TrainingResult) -> bytes:
    """Serialize the complete learned inference artifact for identity.

    The deployable Phase-9 candidate depends on the fitted base model,
    preprocessor, and probability calibrator together. Pickle is used only
    to fingerprint that in-memory fitted state; it is not a deployment
    format and is never loaded by this module.
    """
    try:
        artifact = (
            result.model,
            result.preprocessor,
            result.calibrator,
        )
        return pickle.dumps(artifact, protocol=5)
    except (pickle.PickleError, TypeError) as exc:
        raise TypeError(
            "fitted model could not be serialized for artifact identity"
        ) from exc


__all__ = ["RetrainingResult", "retrain_candidate"]
