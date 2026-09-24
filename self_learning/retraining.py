"""Controlled retraining adapter for the existing Phase-9 trainer.

This module deliberately returns a training result and provenance metadata.
It does not choose a model, mutate a production model, or promote anything.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable

from ml.datasets.models import TrainingDataset
from ml.training.models import TrainingConfig, TrainingResult
from ml.training.trainer import train_baseline, train_random_forest

from .contracts import DatasetVersion, ExperimentSpec


@dataclass(frozen=True, slots=True)
class RetrainingResult:
    """Immutable candidate-training output."""

    model_family: str
    result: TrainingResult
    dataset_version: str
    experiment_fingerprint: str
    artifact_fingerprint: str
    status: str = "CANDIDATE"


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

    The trainer selection is explicit.  No automatic production replacement
    happens here.
    """
    if not isinstance(dataset, TrainingDataset):
        raise TypeError("dataset must be a TrainingDataset")
    if not isinstance(dataset_version, DatasetVersion):
        raise TypeError("dataset_version must be a DatasetVersion")
    if not isinstance(experiment, ExperimentSpec):
        raise TypeError("experiment must be an ExperimentSpec")
    if experiment.dataset_version != dataset_version.dataset_version:
        raise ValueError("experiment and dataset versions do not match")

    config = config or TrainingConfig()

    if trainer == "logistic_regression":
        result = train_baseline(dataset, config)
    elif trainer == "random_forest":
        result = train_random_forest(dataset, config)
    else:
        raise ValueError(f"unsupported candidate trainer: {trainer}")

    serializer = artifact_serializer or _default_artifact_identity
    artifact_fingerprint = serializer(result.model)

    if not isinstance(artifact_fingerprint, str) or len(artifact_fingerprint) != 64:
        raise ValueError("artifact serializer must return a SHA-256 fingerprint")

    return RetrainingResult(
        model_family=trainer,
        result=result,
        dataset_version=dataset_version.dataset_version,
        experiment_fingerprint=experiment.fingerprint,
        artifact_fingerprint=artifact_fingerprint,
    )


def _default_artifact_identity(model: Any) -> str:
    """Return stable identity for a fitted model's parameter representation."""
    if hasattr(model, "get_params"):
        payload = model.get_params(deep=True)
    else:
        payload = repr(model)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["RetrainingResult", "retrain_candidate"]
