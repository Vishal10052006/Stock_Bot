"""Phase 9 stratified evaluation helpers.

These helpers never fit a model. They only slice already-generated
out-of-sample predictions by decision-time metadata.

References:
    PHASE_9_ML.md — predictive-quality evaluation and temporal discipline.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .metrics import (
    evaluate_predictions,
    expected_calibration_error,
    multiclass_brier_score,
)


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
    """Evaluate existing predictions separately for each metadata value.

    The helper consumes already-generated out-of-sample predictions only.
    It never fits or tunes a model.

    Missing metadata values are excluded from the stratified report rather
    than converted into the literal string "nan".
    """
    if column not in metadata.columns:
        raise ValueError(f"metadata is missing required column: {column}")

    if len(y_true) != len(probabilities) or len(y_true) != len(metadata):
        raise ValueError(
            "y_true, probabilities, and metadata must have equal lengths"
        )

    results: list[StratifiedEvaluation] = []

    # Keep missing metadata explicitly missing so it cannot become a fake
    # category named "nan" during string normalization.
    values = metadata[column]
    valid_mask = values.notna()

    for value in sorted(values.loc[valid_mask].astype(str).unique()):
        mask = valid_mask & values.astype(str).eq(value)

        if int(mask.sum()) == 0:
            continue

        positions = mask.to_numpy()
        y_slice = y_true.loc[positions].reset_index(drop=True)
        p_slice = probabilities.loc[positions].reset_index(drop=True)

        metrics = evaluate_predictions(
            y_slice,
            p_slice,
        )
        metrics["sample_count"] = int(mask.sum())
        metrics["brier_score"] = multiclass_brier_score(
            y_slice,
            p_slice,
        )
        metrics["expected_calibration_error"] = expected_calibration_error(
            y_slice,
            p_slice,
        )

        results.append(
            StratifiedEvaluation(
                key=value,
                metrics=metrics,
            )
        )

    return tuple(results)
