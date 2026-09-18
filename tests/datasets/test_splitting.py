"""
Tests for chronological Phase 9 dataset splitting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.features.builder import build_features
from market.indicators.engine import IndicatorEngine

from ml.datasets import (
    TemporalSplitConfig,
    build_training_dataset,
    temporal_split,
)
from ml.labeling import (
    DecisionLabelingOutcome,
    LabelingOutcome,
    PredictionLabel,
    TradeCandidate,
    TradeDirection,
)


def make_features(periods: int = 200) -> pd.DataFrame:
    """Create deterministic FeatureDataset v1."""

    timestamps = pd.date_range(
        "2026-08-03 09:15",
        periods=periods,
        freq="5min",
        tz="Asia/Kolkata",
    )

    base = np.arange(periods, dtype=float)

    candles = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "TEST",
        "open": 100.0 + base * 0.05,
        "high": 100.5 + base * 0.05,
        "low": 99.5 + base * 0.05,
        "close": 100.0 + base * 0.05,
        "volume": 1000.0 + base * 5.0,
    })

    return build_features(
        IndicatorEngine().calculate(candles)
    )


def make_outcome(
    timestamp: pd.Timestamp,
) -> DecisionLabelingOutcome:
    """Create a deterministic NO_EDGE decision label."""

    long_candidate = TradeCandidate(
        timestamp=timestamp,
        symbol="TEST",
        direction=TradeDirection.LONG,
        entry_price=100.0,
        stop_price=98.0,
    )

    short_candidate = TradeCandidate(
        timestamp=timestamp,
        symbol="TEST",
        direction=TradeDirection.SHORT,
        entry_price=100.0,
        stop_price=102.0,
    )

    long_outcome = LabelingOutcome(
        timestamp=timestamp,
        symbol="TEST",
        label=PredictionLabel.NO_EDGE,
        entry_price=100.0,
        stop_price=98.0,
        target_price=103.0,
        horizon_bars=12,
        outcome_timestamp=None,
        outcome_bars=None,
        outcome_reason="TEST",
    )

    short_outcome = LabelingOutcome(
        timestamp=timestamp,
        symbol="TEST",
        label=PredictionLabel.NO_EDGE,
        entry_price=100.0,
        stop_price=102.0,
        target_price=97.0,
        horizon_bars=12,
        outcome_timestamp=None,
        outcome_bars=None,
        outcome_reason="TEST",
    )

    return DecisionLabelingOutcome(
        timestamp=timestamp,
        symbol="TEST",
        label=PredictionLabel.NO_EDGE,
        long_outcome=long_outcome,
        short_outcome=short_outcome,
        outcome_timestamp=None,
        outcome_bars=None,
        outcome_reason="TEST",
    )


def make_dataset(periods: int = 200):
    """Create a deterministic TrainingDataset."""

    features = make_features(periods)

    outcomes = [
        make_outcome(timestamp)
        for timestamp in features["timestamp"]
    ]

    return build_training_dataset(
        features,
        outcomes,
    )


def test_temporal_split_is_chronological():
    """Train must precede validation and validation must precede test."""

    dataset = make_dataset()

    split = temporal_split(dataset)

    assert (
        split.train.data["timestamp"].max()
        < split.validation.data["timestamp"].min()
    )

    assert (
        split.validation.data["timestamp"].max()
        < split.test.data["timestamp"].min()
    )


def test_temporal_split_has_no_timestamp_overlap():
    """Partitions must contain disjoint decision timestamps."""

    split = temporal_split(make_dataset())

    train_times = set(split.train.data["timestamp"])
    validation_times = set(split.validation.data["timestamp"])
    test_times = set(split.test.data["timestamp"])

    assert train_times.isdisjoint(validation_times)
    assert train_times.isdisjoint(test_times)
    assert validation_times.isdisjoint(test_times)


def test_temporal_split_respects_purge_interval():
    """Adjacent partitions must be separated by the purge interval."""

    config = TemporalSplitConfig(
        train_ratio=0.60,
        validation_ratio=0.20,
        test_ratio=0.20,
        purge_minutes=60,
    )

    split = temporal_split(
        make_dataset(),
        config,
    )

    gap_train_validation = (
        split.validation.data["timestamp"].min()
        - split.train.data["timestamp"].max()
    )

    gap_validation_test = (
        split.test.data["timestamp"].min()
        - split.validation.data["timestamp"].max()
    )

    assert gap_train_validation > pd.Timedelta(
        minutes=60
    )

    assert gap_validation_test > pd.Timedelta(
        minutes=60
    )


def test_split_preserves_feature_schema():
    """Every partition must retain the TrainingDataset feature schema."""

    dataset = make_dataset()

    split = temporal_split(dataset)

    assert list(split.train.data.columns) == list(
        dataset.data.columns
    )

    assert list(split.validation.data.columns) == list(
        dataset.data.columns
    )

    assert list(split.test.data.columns) == list(
        dataset.data.columns
    )


def test_split_preserves_label_classes():
    """Labels must remain intact after splitting."""

    dataset = make_dataset()

    split = temporal_split(dataset)

    assert set(split.train.y) == {"NO_EDGE"}
    assert set(split.validation.y) == {"NO_EDGE"}
    assert set(split.test.y) == {"NO_EDGE"}


def test_split_does_not_randomize():
    """Repeated splitting must produce identical partitions."""

    dataset = make_dataset()

    first = temporal_split(dataset)
    second = temporal_split(dataset)

    pd.testing.assert_frame_equal(
        first.train.data,
        second.train.data,
    )

    pd.testing.assert_frame_equal(
        first.validation.data,
        second.validation.data,
    )

    pd.testing.assert_frame_equal(
        first.test.data,
        second.test.data,
    )


def test_invalid_ratios_are_rejected():
    """Split ratios must form a valid partition."""

    with pytest.raises(ValueError):
        TemporalSplitConfig(
            train_ratio=0.8,
            validation_ratio=0.3,
            test_ratio=0.1,
        )


def test_negative_purge_is_rejected():
    """Purge duration cannot be negative."""

    with pytest.raises(ValueError):
        TemporalSplitConfig(
            purge_minutes=-1
        )


def test_too_few_timestamps_are_rejected():
    """A meaningful temporal split requires multiple timestamps."""

    dataset = make_dataset(periods=2)

    with pytest.raises(
        ValueError,
        match="at least three",
    ):
        temporal_split(dataset)


def test_training_rows_are_purged_before_validation_boundary():
    """Training labels must not reach into validation time."""

    config = TemporalSplitConfig(
        train_ratio=0.60,
        validation_ratio=0.20,
        test_ratio=0.20,
        purge_minutes=60,
    )

    split = temporal_split(
        make_dataset(),
        config,
    )

    assert (
        split.train.data["timestamp"].max()
        <= split.train_end
    )

    assert (
        split.validation.data["timestamp"].min()
        > split.validation_start
    )

    assert (
        split.validation.data["timestamp"].min()
        - split.train.data["timestamp"].max()
        > pd.Timedelta(minutes=60)
    )