"""Phase 9 stratified evaluation helpers.

These helpers never fit a model. They only slice already-generated
out-of-sample predictions by decision-time metadata.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .metrics import evaluate_predictions, multiclass_brier_score, expected_calibration_error


@dataclass(frozen=True, slots=True)
class StratifiedEvaluation:
    """Metrics for one deterministic metadata slice."""

    key: str
    metrics: dict[str, object]


def evaluate_by_column(
    y_true: pd.Series,
    probabilities: pd.DataFrame,
    metadata: pd.DataFrame,
    *,
    column: str,
) -> tuple[StratifiedEvaluation, ...]:
    """Evaluate existing predictions separately for each metadata value."""
    if column not in metadata.columns:
        raise ValueError(f"metadata is missing required column: {column}")
    if len(y_true) != len(probabilities) or len(y_true) != len(metadata):
        raise ValueError("y_true, probabilities, and metadata must have equal lengths")

    results: list[StratifiedEvaluation] = []
    values = metadata[column].astype(str)

    for value in sorted(values.dropna().unique()):
        mask = values == value
        if int(mask.sum()) == 0:
            continue
        y_slice = y_true.loc[mask.to_numpy()]
        p_slice = probabilities.loc[mask.to_numpy()].reset_index(drop=True)
        metrics = evaluate_predictions(y_slice.reset_index(drop=True), p_slice)
        metrics["sample_count"] = int(mask.sum())
        metrics["brier_score"] = multiclass_brier_score(y_slice.reset_index(drop=True), p_slice)
        metrics["expected_calibration_error"] = expected_calibration_error(
            y_slice.reset_index(drop=True),
            p_slice,
        )
        results.append(StratifiedEvaluation(key=value, metrics=metrics))

    return tuple(results)
