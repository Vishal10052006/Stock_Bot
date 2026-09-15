"""
TrainingDataset v1 construction for Phase 9.

This module combines:
    - causal FeatureDataset v1
    - decision-level Phase 7 labels

into one supervised learning dataset.

Future information is permitted only through the final label.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from market.features.builder import (
    FEATURE_COLUMNS,
    IDENTIFIER_COLUMNS,
)
from market.features.validation import validate_feature_dataset

from ml.labeling.models import DecisionLabelingOutcome

from .models import TrainingDataset
from .validation import validate_training_dataset


def _outcomes_to_frame(
    outcomes: Iterable[DecisionLabelingOutcome],
) -> pd.DataFrame:
    """Convert decision-level outcomes into a target table."""

    rows = []

    for outcome in outcomes:
        if not isinstance(
            outcome,
            DecisionLabelingOutcome,
        ):
            raise TypeError(
                "TrainingDataset requires "
                "DecisionLabelingOutcome objects."
            )

        rows.append(
            {
                "timestamp": outcome.timestamp,
                "symbol": outcome.symbol,
                "label": outcome.label.value,
            }
        )

    if not rows:
        raise ValueError(
            "At least one decision-level outcome is required."
        )

    return pd.DataFrame(rows)


def build_training_dataset(
    features: pd.DataFrame,
    outcomes: Iterable[DecisionLabelingOutcome],
) -> TrainingDataset:
    """
    Build TrainingDataset v1.

    Parameters
    ----------
    features:
        FeatureDataset v1 containing only decision-time information.

    outcomes:
        Phase 7 decision-level labels. Exactly one outcome must exist
        for each feature observation.

    Returns
    -------
    TrainingDataset
        Supervised dataset containing causal features and one target.
    """

    validated_features = validate_feature_dataset(features)

    outcome_frame = _outcomes_to_frame(outcomes)

    if outcome_frame.duplicated(
        subset=["symbol", "timestamp"],
        keep=False,
    ).any():
        raise ValueError(
            "Decision outcomes contain duplicate "
            "(symbol, timestamp) observations."
        )

    merged = validated_features.merge(
        outcome_frame,
        on=["timestamp", "symbol"],
        how="inner",
        validate="one_to_one",
    )

    if len(merged) != len(validated_features):
        feature_keys = pd.MultiIndex.from_frame(
            validated_features[
                ["symbol", "timestamp"]
            ]
        )

        outcome_keys = pd.MultiIndex.from_frame(
            outcome_frame[
                ["symbol", "timestamp"]
            ]
        )

        missing_mask = ~feature_keys.isin(outcome_keys)

        missing = validated_features.loc[
            missing_mask,
            ["timestamp", "symbol"],
        ]

        raise ValueError(
            "Every FeatureDataset observation must have "
            "exactly one decision-level label. "
            f"Missing labels: {missing.to_dict('records')}"
        )

    ordered_columns = [
        *IDENTIFIER_COLUMNS,
        *FEATURE_COLUMNS,
        "label",
    ]

    result = (
        merged.loc[:, ordered_columns]
        .sort_values(
            ["symbol", "timestamp"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    validated = validate_training_dataset(result)

    return TrainingDataset(
        data=validated,
        feature_columns=FEATURE_COLUMNS,
    )
