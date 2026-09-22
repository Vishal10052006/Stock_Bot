"""Phase 9 model registry metadata contract.

This registry records reproducibility metadata only. It does not promote
models or authorize production trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ModelRegistryRecord:
    """Reproducibility record for one candidate SignalModel."""

    model_version: str
    model_family: str
    feature_version: str
    dataset_version: str
    code_version: str
    training_period_start: str
    training_period_end: str
    validation_period_start: str
    validation_period_end: str
    test_period_start: str
    test_period_end: str
    hyperparameters: Mapping[str, object]
    metrics: Mapping[str, float]
    approval_status: str = "RESEARCH_ONLY"

    def __post_init__(self) -> None:
        """Validate mandatory provenance fields."""
        required = (
            self.model_version,
            self.model_family,
            self.feature_version,
            self.dataset_version,
            self.code_version,
            self.training_period_start,
            self.training_period_end,
            self.validation_period_start,
            self.validation_period_end,
            self.test_period_start,
            self.test_period_end,
        )
        if not all(str(value).strip() for value in required):
            raise ValueError("registry provenance fields must not be empty")

        if self.approval_status not in {"RESEARCH_ONLY", "CANDIDATE", "APPROVED"}:
            raise ValueError("invalid approval_status")
