"""Tests for controlled real-data candidate retraining."""

from __future__ import annotations

import pandas as pd
import pytest

from market.features.builder import FEATURE_COLUMNS
from ml.datasets.models import TrainingDataset
from ml.preprocessing.models import BOOLEAN_FEATURES
from self_learning.contracts import DatasetVersion, ExperimentSpec
from self_learning.dataset import build_dataset_version, dataframe_fingerprint
from self_learning.retraining import (
    _default_artifact_serializer,
    retrain_candidate,
)


def _dataset() -> TrainingDataset:
    # Use the frozen production Phase-9 feature schema rather than synthetic
    # feature names. The retraining adapter must exercise the same
    # preprocessing contract used by the real trainer.
    #
    # The production splitter uses a 60-minute purge on both sides of each
    # boundary, so the fixture also contains enough chronological coverage
    # for train/validation/test partitions to remain non-empty.
    timestamps = pd.date_range(
        "2026-01-01 09:15",
        periods=240,
        freq="5min",
    )
    rows: list[dict[str, object]] = []
    labels = ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")

    for index, timestamp in enumerate(timestamps):
        for symbol_offset, symbol in enumerate(("AAA", "BBB")):
            row: dict[str, object] = {
                "timestamp": timestamp,
                "symbol": symbol,
                "label": labels[(index + symbol_offset) % len(labels)],
            }

            for feature_offset, feature in enumerate(FEATURE_COLUMNS):
                if feature in BOOLEAN_FEATURES:
                    row[feature] = bool(
                        (index + symbol_offset + feature_offset) % 2
                    )
                else:
                    # Deterministic, non-constant numeric values keep the
                    # preprocessing/model contract exercised without using
                    # fabricated market semantics.
                    row[feature] = float(
                        index + symbol_offset + feature_offset * 0.01
                    )

            rows.append(row)

    frame = pd.DataFrame(rows)
    return TrainingDataset(
        data=frame,
        feature_columns=FEATURE_COLUMNS,
    )

