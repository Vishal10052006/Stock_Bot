"""Causality and leakage tests for Phase 5 FeatureDataset."""

from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from market.features.builder import build_features
from market.indicators.engine import IndicatorEngine


def _make_ohlcv() -> pd.DataFrame:
    """Create deterministic intraday OHLCV data."""
    timestamps = pd.date_range(
        "2026-08-31 09:15",
        periods=75,
        freq="5min",
        tz="Asia/Kolkata",
    )

    base = np.arange(75, dtype=float)

    return pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "TEST",
        "open": 100.0 + base * 0.20,
        "high": 100.5 + base * 0.20,
        "low": 99.5 + base * 0.20,
        "close": 100.0 + base * 0.20,
        "volume": 1000.0 + base * 10.0,
    })


def test_future_perturbation_does_not_change_past_features() -> None:
    """Changing future candles must not alter earlier features."""
    cutoff = 50

    original = _make_ohlcv()
    perturbed = original.copy()

    # Modify only candles after the cutoff.
    perturbed.loc[cutoff:, "open"] += 50.0
    perturbed.loc[cutoff:, "high"] += 50.0
    perturbed.loc[cutoff:, "low"] += 50.0
    perturbed.loc[cutoff:, "close"] += 50.0
    perturbed.loc[cutoff:, "volume"] *= 3.0

    engine = IndicatorEngine()

    original_features = build_features(
        engine.calculate(original)
    )

    perturbed_features = build_features(
        engine.calculate(perturbed)
    )

    original_past = original_features.iloc[:cutoff].reset_index(
        drop=True
    )

    perturbed_past = perturbed_features.iloc[:cutoff].reset_index(
        drop=True
    )

    assert_frame_equal(
        original_past,
        perturbed_past,
        check_dtype=True,
        check_exact=True,
    )
