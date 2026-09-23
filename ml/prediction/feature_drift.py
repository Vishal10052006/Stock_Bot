"""Feature-distribution drift diagnostics for Prediction Bot.

This module compares decision-time feature telemetry only. It does not
retrain, recalibrate, alter model weights, or authorize trading.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class FeatureDriftReport:
    """Per-feature distribution drift summary."""

    sample_count_reference: int
    sample_count_current: int
    psi_by_feature: dict[str, float]
    mean_absolute_shift_by_feature: dict[str, float]
    alert_features: tuple[str, ...]
    alert: bool


def _psi(reference: np.ndarray, current: np.ndarray, bins: int) -> float:
    edges = np.quantile(reference, np.linspace(0.0, 1.0, bins + 1))
    edges = np.unique(edges)
    if len(edges) < 2:
        return 0.0
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)
    ref = np.maximum(ref_counts / len(reference), 1e-6)
    cur = np.maximum(cur_counts / len(current), 1e-6)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def compare_feature_distributions(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    *,
    psi_threshold: float = 0.20,
    bins: int = 10,
) -> FeatureDriftReport:
    """Compare finite numeric feature distributions."""
    if not isinstance(reference, pd.DataFrame) or not isinstance(current, pd.DataFrame):
        raise TypeError("reference and current must be pandas DataFrames")
    if reference.empty or current.empty:
        raise ValueError("reference and current must be non-empty")
    if list(reference.columns) != list(current.columns) or not reference.columns.tolist():
        raise ValueError("reference and current must have identical non-empty columns")
    if psi_threshold < 0.0:
        raise ValueError("psi_threshold must be non-negative")
    if bins < 2:
        raise ValueError("bins must be at least 2")

    psi_by_feature: dict[str, float] = {}
    shifts: dict[str, float] = {}

    for column in reference.columns:
        ref = pd.to_numeric(reference[column], errors="coerce").to_numpy(dtype=float)
        cur = pd.to_numeric(current[column], errors="coerce").to_numpy(dtype=float)
        ref = ref[np.isfinite(ref)]
        cur = cur[np.isfinite(cur)]
        if len(ref) == 0 or len(cur) == 0:
            raise ValueError(f"feature '{column}' has no finite observations")
        psi_by_feature[column] = _psi(ref, cur, bins)
        shifts[column] = float(abs(cur.mean() - ref.mean()))

    alerts = tuple(
        sorted(
            column
            for column, value in psi_by_feature.items()
            if value >= psi_threshold
        )
    )
    return FeatureDriftReport(
        sample_count_reference=len(reference),
        sample_count_current=len(current),
        psi_by_feature=psi_by_feature,
        mean_absolute_shift_by_feature=shifts,
        alert_features=alerts,
        alert=bool(alerts),
    )
