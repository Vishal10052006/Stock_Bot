"""
Core models for Phase 9 preprocessing.

The preprocessing configuration describes how causal feature columns
are transformed before entering the ML model.

Important:
    Fitting of learned transformations must happen only on training data.
"""

from __future__ import annotations

from dataclasses import dataclass

from market.features.builder import (
    FEATURE_COLUMNS,
)


BOOLEAN_FEATURES: frozenset[str] = frozenset({
    "retest_up",
    "retest_down",
    "higher_high",
    "lower_low",
    "higher_low",
    "lower_high",
})

NUMERIC_FEATURES: tuple[str, ...] = tuple(
    column
    for column in FEATURE_COLUMNS
    if column not in BOOLEAN_FEATURES
)


@dataclass(frozen=True)
class PreprocessingConfig:
    """
    Configuration for the Phase 9 preprocessing pipeline.

    Numeric features:
        - missing values are imputed using the training median
        - values are standardized using training statistics

    Boolean features:
        - missing values are imputed using the training most-frequent value
        - values are converted to numeric 0/1 representation

    All learned statistics must come exclusively from training data.
    """

    numeric_strategy: str = "median"
    boolean_strategy: str = "most_frequent"
    scale_numeric: bool = True

    def __post_init__(self) -> None:
        """Validate preprocessing configuration."""

        if self.numeric_strategy != "median":
            raise ValueError(
                "numeric_strategy must be 'median'."
            )

        if self.boolean_strategy != "most_frequent":
            raise ValueError(
                "boolean_strategy must be 'most_frequent'."
            )


@dataclass(frozen=True)
class PreprocessingResult:
    """
    Metadata describing a fitted preprocessing transformation.

    The fitted sklearn transformer itself is intentionally kept outside
    this immutable configuration model.
    """

    feature_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...]
    boolean_columns: tuple[str, ...]
    fitted_on_rows: int

    def __post_init__(self) -> None:
        """Validate preprocessing result metadata."""

        if not self.feature_columns:
            raise ValueError(
                "feature_columns must not be empty."
            )

        if self.fitted_on_rows <= 0:
            raise ValueError(
                "fitted_on_rows must be greater than 0."
            )
