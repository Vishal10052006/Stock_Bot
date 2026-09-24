"""Controlled retraining adapter built on the existing Phase-9 trainer.

Retraining produces a research candidate only. It does not register, approve,
promote, or deploy the candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ml.datasets.models import TrainingDataset
from ml.training.models import TrainingConfig, TrainingResult
from ml.training.trainer import train_baseline


@dataclass(frozen=True, slots=True)
class RetrainingResult:
    """Immutable result of one controlled training invocation."""

    model_version: str
    dataset_version: str
    training_result: TrainingResult
    parent_model_version: str | None
    trigger_reason: str

    def __post_init__(self) -> None:
        if not self.model_version.strip():
            raise ValueError("model_version must be non-empty")
        if not self.dataset_version.strip():
            raise ValueError("dataset_version must be non-empty")
        if not self.trigger_reason.strip():
            raise ValueError("trigger_reason must be non-empty")


class ControlledRetrainer:
    """Single-entry adapter enforcing explicit candidate metadata."""

    def retrain(
        self,
        dataset: TrainingDataset,
        *,
        dataset_version: str,
        candidate_model_version: str,
        parent_model_version: str | None,
        trigger_reason: str,
        config: TrainingConfig | None = None,
        trainer: Callable[
            [TrainingDataset, TrainingConfig | None],
            TrainingResult,
        ]
        | None = None,
    ) -> RetrainingResult:
        """Train one candidate through the existing Phase-9 trainer."""
        if not isinstance(dataset, TrainingDataset):
            raise TypeError("dataset must be a TrainingDataset")

        trainer_fn = trainer or train_baseline
        result = trainer_fn(dataset, config)

        return RetrainingResult(
            model_version=candidate_model_version,
            dataset_version=dataset_version,
            training_result=result,
            parent_model_version=parent_model_version,
            trigger_reason=trigger_reason,
        )
