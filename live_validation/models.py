"""Contracts for real-market prediction outcome validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ml.models.logistic import MODEL_CLASSES


class OutcomeStatus(str, Enum):
    """Lifecycle state of one live prediction observation."""

    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class LivePrediction:
    """Prediction snapshot plus immutable causal candidate evidence."""

    prediction_id: str
    timestamp: pd.Timestamp
    symbol: str
    model_version: str
    feature_version: str
    dataset_version: str
    predicted_class: str
    probabilities: Mapping[str, float]
    generated_at: pd.Timestamp
    horizon_bars: int
    target_r_multiple: float
    long_entry_price: float
    long_stop_price: float
    short_entry_price: float
    short_stop_price: float

    def __post_init__(self) -> None:
        timestamp = pd.Timestamp(self.timestamp)
        generated_at = pd.Timestamp(self.generated_at)
        if timestamp.tzinfo is None or generated_at.tzinfo is None:
            raise ValueError("prediction timestamps must be timezone-aware")
        if not str(self.prediction_id).strip():
            raise ValueError("prediction_id must not be empty")
        if not str(self.symbol).strip():
            raise ValueError("symbol must not be empty")
        if self.predicted_class not in MODEL_CLASSES:
            raise ValueError("predicted_class must be a canonical Phase 9 class")
        if self.horizon_bars <= 0:
            raise ValueError("horizon_bars must be positive")
        if not math.isfinite(float(self.target_r_multiple)) or self.target_r_multiple <= 0:
            raise ValueError("target_r_multiple must be finite and positive")
        for name, value in (
            ("long_entry_price", self.long_entry_price),
            ("long_stop_price", self.long_stop_price),
            ("short_entry_price", self.short_entry_price),
            ("short_stop_price", self.short_stop_price),
        ):
            if not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not self.long_stop_price < self.long_entry_price:
            raise ValueError("long_stop_price must be below long_entry_price")
        if not self.short_stop_price > self.short_entry_price:
            raise ValueError("short_stop_price must be above short_entry_price")

        values = {str(key): float(value) for key, value in self.probabilities.items()}
        if tuple(values) != MODEL_CLASSES:
            raise ValueError("probabilities must use canonical Phase 9 class order")
        if not np.isfinite(np.asarray(tuple(values.values()), dtype=float)).all():
            raise ValueError("probabilities must be finite")
        if any(value < 0.0 or value > 1.0 for value in values.values()):
            raise ValueError("probabilities must lie in [0, 1]")
        if abs(sum(values.values()) - 1.0) > 1e-8:
            raise ValueError("probabilities must sum to 1")

        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "symbol", str(self.symbol).strip().upper())
        object.__setattr__(self, "probabilities", dict(values))


@dataclass(frozen=True, slots=True)
class LiveOutcome:
    """Resolved Phase 7 outcome linked to one live prediction."""

    prediction_id: str
    status: OutcomeStatus
    actual_class: str | None = None
    outcome_timestamp: pd.Timestamp | None = None
    outcome_bars: int | None = None
    outcome_reason: str | None = None
    resolved_at: pd.Timestamp | None = None

    def __post_init__(self) -> None:
        if not str(self.prediction_id).strip():
            raise ValueError("prediction_id must not be empty")
        if self.status is OutcomeStatus.RESOLVED:
            if self.actual_class not in MODEL_CLASSES:
                raise ValueError("resolved outcome must use a canonical Phase 9 class")
            if self.outcome_timestamp is None or pd.Timestamp(self.outcome_timestamp).tzinfo is None:
                raise ValueError("resolved outcome requires timezone-aware outcome_timestamp")
            if self.outcome_bars is None or self.outcome_bars <= 0:
                raise ValueError("resolved outcome requires positive outcome_bars")
            if not str(self.outcome_reason or "").strip():
                raise ValueError("resolved outcome requires outcome_reason")
            if self.resolved_at is None or pd.Timestamp(self.resolved_at).tzinfo is None:
                raise ValueError("resolved outcome requires timezone-aware resolved_at")
        else:
            if any(value is not None for value in (
                self.actual_class,
                self.outcome_timestamp,
                self.outcome_bars,
                self.outcome_reason,
                self.resolved_at,
            )):
                raise ValueError("pending outcome must not contain resolution fields")


@dataclass(frozen=True, slots=True)
class LivePredictionReport:
    """Aggregate report across a live prediction-validation journal."""

    total_predictions: int
    resolved_predictions: int
    pending_predictions: int
    correct_predictions: int
    incorrect_predictions: int
    accuracy: float | None
    class_totals: Mapping[str, int]
    class_correct: Mapping[str, int]
    class_incorrect: Mapping[str, int]
    confusion_matrix: np.ndarray

    def __post_init__(self) -> None:
        if self.total_predictions < 0:
            raise ValueError("total_predictions must not be negative")
        if self.resolved_predictions < 0 or self.pending_predictions < 0:
            raise ValueError("prediction counts must not be negative")
        if self.resolved_predictions + self.pending_predictions != self.total_predictions:
            raise ValueError("resolved + pending must equal total predictions")
        if self.correct_predictions < 0 or self.incorrect_predictions < 0:
            raise ValueError("correct/incorrect counts must not be negative")
        if self.correct_predictions + self.incorrect_predictions != self.resolved_predictions:
            raise ValueError("correct + incorrect must equal resolved predictions")
        if self.accuracy is not None and not 0.0 <= float(self.accuracy) <= 1.0:
            raise ValueError("accuracy must lie in [0, 1]")
        for mapping in (self.class_totals, self.class_correct, self.class_incorrect):
            if tuple(mapping) != MODEL_CLASSES:
                raise ValueError("class mappings must use canonical Phase 9 class order")
            if any(int(value) < 0 for value in mapping.values()):
                raise ValueError("class counts must not be negative")
        matrix = np.asarray(self.confusion_matrix)
        if matrix.shape != (len(MODEL_CLASSES), len(MODEL_CLASSES)):
            raise ValueError("confusion_matrix has an invalid shape")
        if not np.isfinite(matrix.astype(float)).all() or (matrix < 0).any():
            raise ValueError("confusion_matrix must contain non-negative finite values")
        if int(matrix.sum()) != self.resolved_predictions:
            raise ValueError("confusion_matrix total must equal resolved_predictions")

    def to_mapping(self) -> dict[str, Any]:
        """Return JSON-safe report data."""
        return {
            "total_predictions": self.total_predictions,
            "resolved_predictions": self.resolved_predictions,
            "pending_predictions": self.pending_predictions,
            "correct_predictions": self.correct_predictions,
            "incorrect_predictions": self.incorrect_predictions,
            "accuracy": self.accuracy,
            "class_totals": dict(self.class_totals),
            "class_correct": dict(self.class_correct),
            "class_incorrect": dict(self.class_incorrect),
            "confusion_matrix": self.confusion_matrix.astype(int).tolist(),
        }
