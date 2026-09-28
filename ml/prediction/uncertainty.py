"""Model-agnostic uncertainty diagnostics for probability predictions.

These measures quantify predictive uncertainty; they are not confidence in
profitability and must not be interpreted as a trade authorization signal.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.models.logistic import MODEL_CLASSES


def predictive_entropy(probabilities: pd.DataFrame) -> pd.Series:
    """Return Shannon entropy for each canonical probability row."""
    values = _validate(probabilities)
    entropy = -np.sum(values * np.log(np.clip(values, 1e-12, 1.0)), axis=1)
    return pd.Series(entropy, index=probabilities.index, name="predictive_entropy")


def probability_margin(probabilities: pd.DataFrame) -> pd.Series:
    """Return the gap between the largest and second-largest probability."""
    values = _validate(probabilities)
    ordered = np.sort(values, axis=1)
    margin = ordered[:, -1] - ordered[:, -2]
    return pd.Series(margin, index=probabilities.index, name="probability_margin")


def variation_ratio(probabilities: pd.DataFrame) -> pd.Series:
    """Return 1 - max probability as a simple classification ambiguity measure."""
    values = _validate(probabilities)
    result = 1.0 - values.max(axis=1)
    return pd.Series(result, index=probabilities.index, name="variation_ratio")


def _validate(probabilities: pd.DataFrame) -> np.ndarray:
    if not isinstance(probabilities, pd.DataFrame):
        raise TypeError("probabilities must be a pandas DataFrame")
    if list(probabilities.columns) != list(MODEL_CLASSES):
        raise ValueError("probabilities must use the canonical class order")
    values = probabilities.to_numpy(dtype=float)
    if values.ndim != 2 or len(values) == 0:
        raise ValueError("probabilities must be a non-empty two-dimensional matrix")
    if not np.isfinite(values).all():
        raise ValueError("probabilities must be finite")
    if (values < 0).any() or (values > 1).any():
        raise ValueError("probabilities must lie in [0, 1]")
    if not np.allclose(values.sum(axis=1), 1.0, atol=1e-8):
        raise ValueError("probability rows must sum to 1")
    return values
