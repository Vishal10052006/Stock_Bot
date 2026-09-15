"""
Tests for Phase 9 TrainingDataset v1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from market.features.builder import build_features
from market.indicators.engine import IndicatorEngine

from ml.datasets import (
    build_training_dataset,
    validate_training_dataset,
)
from ml.labeling import (
    DecisionLabelingOutcome,
    LabelingOutcome,
    PredictionLabel,
    TradeCandidate,
    TradeDirection,
    label_decision,
)


def make_features() -> pd.DataFrame:
    """Build deterministic valid FeatureDataset v1."""

    timestamps = pd.date_range(
        "2026-09-01 09:15",
        periods=75,
        freq="5min",
        tz="Asia/Kolkata",
    )

    base = np.arange(75, dtype=float)

    candles = pd.DataFrame({
        "timestamp": timestamps,
        "symbol": "TEST",
        "open": 100.0 + base * 0.20,
        "high": 100.5 + base * 0.20,
        "low": 99.5 + base * 0.20,
        "close": 100.0 + base * 0.20,
        "volume": 1000.0 + base * 10.0,
    })

    indicators = IndicatorEngine().calculate(
        candles
    )

    return build_features(indicators)


def make_outcome(
    timestamp: pd.Timestamp,
    label: PredictionLabel,
) -> DecisionLabelingOutcome:
    """Create a deterministic decision-level outcome."""

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
        label=(
            PredictionLabel.LONG_SUCCESS
            if label == PredictionLabel.LONG_SUCCESS
            else PredictionLabel.NO_EDGE
        ),
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
        label=(
            PredictionLabel.SHORT_SUCCESS
            if label == PredictionLabel.SHORT_SUCCESS
            else PredictionLabel.NO_EDGE
        ),
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
        label=label,
        long_outcome=long_outcome,
        short_outcome=short_outcome,
        outcome_timestamp=None,
        outcome_bars=None,
        outcome_reason="TEST",
    )


def test_training_dataset_schema():
    """TrainingDataset must contain only identifiers, features and label."""

    features = make_features()

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.NO_EDGE,
        )
        for timestamp in features["timestamp"]
    ]

    dataset = build_training_dataset(
        features,
        outcomes,
    )

    assert len(dataset.data) == len(features)
    assert tuple(dataset.data.columns) == (
        "timestamp",
        "symbol",
        *features.columns[2:],
        "label",
    )


def test_training_dataset_has_one_row_per_decision():
    """Each decision timestamp must map to exactly one target."""

    features = make_features()

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.LONG_SUCCESS,
        )
        for timestamp in features["timestamp"]
    ]

    dataset = build_training_dataset(
        features,
        outcomes,
    )

    assert not dataset.data.duplicated(
        ["symbol", "timestamp"]
    ).any()


def test_training_dataset_exposes_x_and_y():
    """X must contain features only and y only the target."""

    features = make_features()

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.SHORT_SUCCESS,
        )
        for timestamp in features["timestamp"]
    ]

    dataset = build_training_dataset(
        features,
        outcomes,
    )

    assert list(dataset.X.columns) == list(
        features.columns[2:]
    )

    assert len(dataset.y) == len(features)

    assert set(dataset.y) == {
        "SHORT_SUCCESS"
    }


def test_missing_decision_label_is_rejected():
    """Every feature observation requires exactly one label."""

    features = make_features()

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.NO_EDGE,
        )
        for timestamp in features["timestamp"][:-1]
    ]

    with pytest.raises(
        ValueError,
        match="Every FeatureDataset observation",
    ):
        build_training_dataset(
            features,
            outcomes,
        )


def test_duplicate_decision_label_is_rejected():
    """Two labels for one decision are invalid."""

    features = make_features()

    timestamp = features.iloc[0]["timestamp"]

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.LONG_SUCCESS,
        ),
        make_outcome(
            timestamp,
            PredictionLabel.SHORT_SUCCESS,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        build_training_dataset(
            features.iloc[[0]],
            outcomes,
        )


def test_future_metadata_is_not_in_training_schema():
    """Future outcome metadata must never enter the ML dataset."""

    features = make_features()

    outcomes = [
        make_outcome(
            timestamp,
            PredictionLabel.NO_EDGE,
        )
        for timestamp in features["timestamp"]
    ]

    dataset = build_training_dataset(
        features,
        outcomes,
    )

    forbidden = {
        "outcome_timestamp",
        "outcome_bars",
        "outcome_reason",
        "target_price",
        "stop_price",
        "future_close",
        "future_high",
        "future_low",
    }

    assert forbidden.isdisjoint(
        dataset.data.columns
    )


def test_invalid_training_label_is_rejected():
    """Only the three frozen decision labels are allowed."""

    features = make_features()

    data = features.copy()
    data["label"] = "INVALID"

    with pytest.raises(
        ValueError,
        match="invalid labels",
    ):
        validate_training_dataset(data)
