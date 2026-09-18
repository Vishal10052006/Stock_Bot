"""Validation contract tests for Phase 5 FeatureDataset v1."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.features.builder import build_features
from market.features.validation import validate_feature_dataset
from market.indicators.engine import IndicatorEngine


def _make_features() -> pd.DataFrame:
    """Create deterministic valid FeatureDataset v1 data."""
    timestamps = pd.date_range(
        "2026-08-31 09:15",
        periods=75,
        freq="5min",
        tz="Asia/Kolkata",
    )

    base = np.arange(75, dtype=float)

    data = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "TEST",
        "open": 100.0 + base * 0.20,
        "high": 100.5 + base * 0.20,
        "low": 99.5 + base * 0.20,
        "close": 100.0 + base * 0.20,
        "volume": 1000.0 + base * 10.0,
    })

    indicators = IndicatorEngine().calculate(data)

    return build_features(indicators)


def test_valid_feature_dataset_passes() -> None:
    """A valid FeatureDataset must pass validation."""
    features = _make_features()

    validated = validate_feature_dataset(features)

    assert len(validated) == 75
    assert validated.columns.equals(features.columns)


def test_missing_feature_is_rejected() -> None:
    """Missing required feature must be rejected."""
    features = _make_features().drop(columns=["rsi_14"])

    with pytest.raises(ValueError, match="missing columns"):
        validate_feature_dataset(features)


def test_unexpected_feature_is_rejected() -> None:
    """Unexpected feature must be rejected."""
    features = _make_features()
    features["unexpected_feature"] = 1.0

    with pytest.raises(ValueError, match="unexpected columns"):
        validate_feature_dataset(features)


def test_duplicate_observation_is_rejected() -> None:
    """Duplicate symbol/timestamp observations must be rejected."""
    features = _make_features()

    duplicate = pd.concat(
        [features, features.iloc[[10]]],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="duplicate FeatureDataset observations",
    ):
        validate_feature_dataset(duplicate)


def test_timezone_naive_timestamp_is_rejected() -> None:
    """Timezone-naive timestamps must be rejected."""
    features = _make_features()

    features["timestamp"] = (
        features["timestamp"]
        .dt.tz_localize(None)
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        validate_feature_dataset(features)


def test_out_of_order_timestamps_are_rejected() -> None:
    """Observations must remain chronological within each symbol."""
    features = _make_features()

    features.iloc[[10, 11]] = (
        features.iloc[[11, 10]].to_numpy()
    )

    with pytest.raises(
        ValueError,
        match="chronologically ordered",
    ):
        validate_feature_dataset(features)


def test_infinite_numeric_value_is_rejected() -> None:
    """Infinite feature values must be rejected."""
    features = _make_features()
    features.loc[20, "rsi_14"] = np.inf

    with pytest.raises(
        ValueError,
        match="infinite numeric values",
    ):
        validate_feature_dataset(features)


def test_wrong_boolean_dtype_is_rejected() -> None:
    """Structure features must retain boolean dtype."""
    features = _make_features()

    features["higher_high"] = (
        features["higher_high"].astype(object)
    )

    with pytest.raises(
        TypeError,
        match="higher_high must use a boolean dtype",
    ):
        validate_feature_dataset(features)


def test_target_column_is_rejected() -> None:
    """Target/label information must not enter FeatureDataset."""
    features = _make_features()
    features["target"] = 1

    with pytest.raises(
        ValueError,
        match="unexpected columns",
    ):
        validate_feature_dataset(features)


def test_missing_symbol_is_rejected() -> None:
    """Symbol identifier must never be missing."""
    features = _make_features()
    features.loc[5, "symbol"] = None

    with pytest.raises(
        ValueError,
        match="symbol must not contain missing values",
    ):
        validate_feature_dataset(features)


def test_missing_timestamp_is_rejected() -> None:
    """Timestamp identifier must never be missing."""
    features = _make_features()
    features.loc[5, "timestamp"] = pd.NaT

    with pytest.raises(
        ValueError,
        match="timestamp must not contain missing values",
    ):
        validate_feature_dataset(features)
