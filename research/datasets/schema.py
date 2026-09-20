"""Versioned point-in-time research dataset contract."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ResearchDatasetRow:
    dataset_version: str
    symbol: str
    decision_time: datetime
    feature_available_at: datetime
    features: Mapping[str, float]
    label: str | None = None
    label_available_at: datetime | None = None
    source_document_ids: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.feature_available_at > self.decision_time:
            raise ValueError("dataset row contains future research information")
        if self.label_available_at is not None and self.label_available_at < self.decision_time:
            raise ValueError("label_available_at cannot precede decision_time")
        forbidden = {key.lower() for key in self.features} & {
            "label", "future_return", "future_price", "target_price", "outcome_timestamp"
        }
        if forbidden:
            raise ValueError(f"target fields in research features: {sorted(forbidden)}")
