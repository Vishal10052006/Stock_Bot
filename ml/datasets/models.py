"""
Core models for Phase 9 TrainingDataset v1.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TrainingDataset:
    """
    Immutable wrapper around the supervised ML dataset.

    The dataset contains:
        - decision-time identifiers
        - causal feature columns
        - exactly one decision-level prediction label

    Future outcome metadata is deliberately excluded.
    """

    data: pd.DataFrame
    feature_columns: tuple[str, ...]
    label_column: str = "label"

    def __post_init__(self) -> None:
        """Validate basic construction invariants."""

        if not isinstance(self.data, pd.DataFrame):
            raise TypeError(
                "data must be a pandas DataFrame."
            )

        if not self.feature_columns:
            raise ValueError(
                "feature_columns must not be empty."
            )

        if self.label_column not in self.data.columns:
            raise ValueError(
                f"Missing label column '{self.label_column}'."
            )

        missing_features = [
            column
            for column in self.feature_columns
            if column not in self.data.columns
        ]

        if missing_features:
            raise ValueError(
                "TrainingDataset is missing feature columns: "
                f"{missing_features}"
            )

    @property
    def X(self) -> pd.DataFrame:
        """Return the causal ML feature matrix."""

        return self.data.loc[:, list(self.feature_columns)].copy()

    @property
    def y(self) -> pd.Series:
        """Return the decision-level prediction target."""

        return self.data[self.label_column].copy()

    @property
    def identifiers(self) -> pd.DataFrame:
        """Return decision identifiers."""

        return self.data.loc[
            :,
            ["timestamp", "symbol"],
        ].copy()
