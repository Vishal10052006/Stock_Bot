"""Validation for Phase 6 regime datasets."""
from __future__ import annotations

import numpy as np
import pandas as pd

from market.regime.models import MarketRegime, REGIME_OUTPUT_COLUMNS


def validate_regime_dataset(data: pd.DataFrame) -> None:
    """Validate the frozen ``timestamp/regime/regime_probability`` schema."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    missing = set(REGIME_OUTPUT_COLUMNS).difference(data.columns)
    if missing:
        raise ValueError(f"missing regime columns: {sorted(missing)}")
    if data["timestamp"].duplicated().any():
        raise ValueError("regime timestamps must be unique")
    if not isinstance(data["timestamp"].dtype, pd.DatetimeTZDtype):
        raise ValueError("regime timestamp must be timezone-aware")
    if not data["timestamp"].is_monotonic_increasing:
        raise ValueError("regime timestamps must be chronological")

    allowed = {regime.value for regime in MarketRegime}
    observed = set(data["regime"].dropna().astype(str))
    unexpected = observed.difference(allowed)
    if unexpected:
        raise ValueError(f"unexpected regime values: {sorted(unexpected)}")

    probability = pd.to_numeric(data["regime_probability"], errors="coerce")
    invalid = probability.notna() & ((probability < 0.0) | (probability > 1.0))
    if invalid.any():
        raise ValueError("regime_probability must be between 0 and 1")
    if np.isinf(probability.dropna().to_numpy()).any():
        raise ValueError("regime_probability must not contain infinite values")

    available = data["regime"].notna()
    if (available & probability.isna()).any():
        raise ValueError("classified regimes must have regime_probability")
