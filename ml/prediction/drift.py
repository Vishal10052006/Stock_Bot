"""Prediction-distribution drift diagnostics.

The functions compare already-generated prediction telemetry.  They never
retrain, recalibrate, or alter a model.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd

from ml.models.logistic import MODEL_CLASSES


@dataclass(frozen=True, slots=True)
class PredictionDriftReport:
    """Distribution drift for canonical prediction probabilities."""

    sample_count_reference: int
    sample_count_current: int
    class_mean_absolute_shift: dict[str, float]
    probability_psi: dict[str, float]
    alert: bool


def _psi(reference: np.ndarray, current: np.ndarray, bins: int) -> float:
    if len(reference) == 0 or len(current) == 0:
        raise ValueError("reference and current samples must be non-empty")
    if bins < 2:
        raise ValueError("bins must be at least 2")

    edges = np.linspace(0.0, 1.0, bins + 1)
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)

    ref = np.maximum(ref_counts / len(reference), 1e-6)
    cur = np.maximum(cur_counts / len(current), 1e-6)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def compare_prediction_distributions(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    psi_threshold: float = 0.20,
    bins: int = 10,
) -> PredictionDriftReport:
    """Compare probability distributions without taking model actions."""
    if not 0.0 <= psi_threshold:
        raise ValueError("psi_threshold must be non-negative")
    required = set(MODEL_CLASSES)
    if set(reference.columns) != required or set(current.columns) != required:
        raise ValueError("reference/current must contain exactly the canonical classes")

    ref = reference.loc[:, list(MODEL_CLASSES)].to_numpy(dtype=float)
    cur = current.loc[:, list(MODEL_CLASSES)].to_numpy(dtype=float)
    if len(ref) == 0 or len(cur) == 0:
        raise ValueError("reference and current must be non-empty")
    if not np.isfinite(ref).all() or not np.isfinite(cur).all():
        raise ValueError("prediction probabilities must be finite")
    if not np.allclose(ref.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("reference probability rows must sum to 1")
    if not np.allclose(cur.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("current probability rows must sum to 1")

    shifts = {
        label: float(abs(cur[:, index].mean() - ref[:, index].mean()))
        for index, label in enumerate(MODEL_CLASSES)
    }
    psi = {
        label: _psi(ref[:, index], cur[:, index], bins)
        for index, label in enumerate(MODEL_CLASSES)
    }
    return PredictionDriftReport(
        sample_count_reference=len(ref),
        sample_count_current=len(cur),
        class_mean_absolute_shift=shifts,
        probability_psi=psi,
        alert=bool(any(value >= psi_threshold for value in psi.values())),
    )
