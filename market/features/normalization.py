"""Deterministic normalization utilities for STOCK BOT features.

Phase 5 rules:
    - No trainable scaler is fitted here.
    - No future information is used.
    - Market-relative transformations are deterministic.
    - NaN values remain NaN.
    - Infinite values are converted to NaN.

References:
    ROADMAP_STOCK-BOT.pdf — Phase 5, Feature Engineering.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalize_by_price(
    value: pd.Series,
    price: pd.Series,
) -> pd.Series:
    """Normalize a price-scale series by the current close."""
    value = value.astype(float)
    price = price.astype(float)

    safe_price = price.mask(price == 0, np.nan)

    result = value.div(safe_price)

    return result.replace(
        [np.inf, -np.inf],
        np.nan,
    )


def normalize_distance_pct(
    value: pd.Series,
) -> pd.Series:
    """Preserve an already price-normalized percentage feature."""
    result = value.astype(float)

    return result.replace(
        [np.inf, -np.inf],
        np.nan,
    )


def normalize_boolean(
    value: pd.Series,
) -> pd.Series:
    """Preserve nullable boolean features."""
    return value.astype("boolean")


def sanitize_numeric(
    value: pd.Series,
) -> pd.Series:
    """Convert numeric input to float and remove infinite values."""
    result = value.astype(float)

    return result.replace(
        [np.inf, -np.inf],
        np.nan,
    )


def sanitize_feature_dataset(
    data: pd.DataFrame,
) -> pd.DataFrame:
    """Sanitize numeric and boolean columns without filling NaNs."""
    result = data.copy()

    for column in result.columns:
        if pd.api.types.is_bool_dtype(result[column]):
            result[column] = normalize_boolean(result[column])

        elif pd.api.types.is_numeric_dtype(result[column]):
            result[column] = sanitize_numeric(result[column])

    return result
