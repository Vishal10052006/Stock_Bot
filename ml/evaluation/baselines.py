"""Phase 9 benchmark baselines.

References:
    docs/PHASE_9_SPEC.md
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.models.logistic import MODEL_CLASSES


@dataclass(frozen=True, slots=True)
class ProbabilityBaseline:
    """A deterministic probability baseline evaluated without fitting ML."""

    name: str
    probabilities: pd.DataFrame


def majority_class(y: pd.Series) -> str:
    """Return the deterministic majority class with canonical tie-breaking."""
    counts = y.astype(str).value_counts()
    max_count = int(counts.max())
    candidates = set(counts[counts == max_count].index.astype(str))
    for label in MODEL_CLASSES:
        if label in candidates:
            return label
    raise ValueError("no valid Phase 9 labels found")


def class_prior_probabilities(y_train: pd.Series, rows: int) -> pd.DataFrame:
    """Create a constant class-prior probability baseline from training only."""
    if rows <= 0:
        raise ValueError("rows must be greater than zero")

    values = {
        label: float((y_train.astype(str) == label).mean())
        for label in MODEL_CLASSES
    }

    probabilities = pd.DataFrame(
        np.tile(
            [values[label] for label in MODEL_CLASSES],
            (rows, 1),
        ),
        columns=list(MODEL_CLASSES),
    )
    return probabilities


def majority_probabilities(
    y_train: pd.Series,
    rows: int,
) -> pd.DataFrame:
    """Return a one-hot majority-class probability baseline."""
    if rows <= 0:
        raise ValueError("rows must be greater than zero")

    label = majority_class(y_train)
    values = np.zeros((rows, len(MODEL_CLASSES)), dtype=float)
    values[:, MODEL_CLASSES.index(label)] = 1.0
    return pd.DataFrame(values, columns=list(MODEL_CLASSES))
