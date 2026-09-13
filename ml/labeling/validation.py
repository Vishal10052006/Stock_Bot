"""
Validation utilities for Phase 7 prediction-target labeling.

These checks enforce the structural and causality assumptions required
before a labeling result can be trusted for research or ML training.
"""

from __future__ import annotations

import pandas as pd

from .models import TradeCandidate


REQUIRED_CANDLE_COLUMNS = {
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
}


def validate_candle_frame(candles: pd.DataFrame) -> None:
    """
    Validate the structural integrity of a candle DataFrame.

    Raises:
        TypeError: If candles is not a DataFrame.
        ValueError: If required columns or valid OHLC data are missing.
    """

    if not isinstance(candles, pd.DataFrame):
        raise TypeError("candles must be a pandas DataFrame.")

    missing = REQUIRED_CANDLE_COLUMNS.difference(candles.columns)

    if missing:
        raise ValueError(
            f"Missing required candle columns: {sorted(missing)}"
        )

    if candles.empty:
        raise ValueError("candles must not be empty.")

    timestamps = pd.to_datetime(
        candles["timestamp"],
        errors="coerce",
    )

    if timestamps.isna().any():
        raise ValueError("candles contains invalid timestamps.")

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
    ]

    for column in numeric_columns:
        values = pd.to_numeric(
            candles[column],
            errors="coerce",
        )

        if values.isna().any():
            raise ValueError(
                f"candles contains invalid values in '{column}'."
            )

    high = pd.to_numeric(candles["high"], errors="coerce")
    low = pd.to_numeric(candles["low"], errors="coerce")

    if (high < low).any():
        raise ValueError(
            "Candle high cannot be lower than candle low."
        )


def validate_candidate_against_candles(
    candles: pd.DataFrame,
    candidate: TradeCandidate,
) -> None:
    """
    Verify that a candidate has a valid decision-time relationship
    with its candle series.

    The candidate timestamp itself may exist in the candle frame,
    but future outcome evaluation must only use timestamps strictly
    greater than the candidate timestamp.
    """

    validate_candle_frame(candles)

    symbol_mask = (
        candles["symbol"].astype(str) == candidate.symbol
    )

    symbol_candles = candles.loc[symbol_mask]

    if symbol_candles.empty:
        raise ValueError(
            f"No candle data found for symbol '{candidate.symbol}'."
        )

    timestamps = pd.to_datetime(
        symbol_candles["timestamp"],
        errors="coerce",
    )

    if timestamps.duplicated().any():
        raise ValueError(
            "Duplicate timestamps detected for candidate symbol."
        )

    if not (timestamps > candidate.timestamp).any():
        raise ValueError(
            "Candidate has no future candles available for labeling."
        )


def validate_labeling_output(
    output: pd.DataFrame,
) -> None:
    """
    Validate the schema and basic invariants of labeling output.
    """

    required_columns = {
        "timestamp",
        "symbol",
        "label",
        "entry_price",
        "stop_price",
        "target_price",
        "horizon_bars",
        "outcome_timestamp",
        "outcome_bars",
        "outcome_reason",
    }

    if not isinstance(output, pd.DataFrame):
        raise TypeError("output must be a pandas DataFrame.")

    missing = required_columns.difference(output.columns)

    if missing:
        raise ValueError(
            f"Labeling output is missing columns: {sorted(missing)}"
        )

    valid_labels = {
        "LONG_SUCCESS",
        "SHORT_SUCCESS",
        "NO_EDGE",
    }

    invalid_labels = set(output["label"].dropna()) - valid_labels

    if invalid_labels:
        raise ValueError(
            f"Invalid prediction labels: {sorted(invalid_labels)}"
        )

    if (output["entry_price"] <= 0).any():
        raise ValueError("Output contains invalid entry prices.")

    if (output["stop_price"] <= 0).any():
        raise ValueError("Output contains invalid stop prices.")

    if (output["target_price"] <= 0).any():
        raise ValueError("Output contains invalid target prices.")

    if (output["horizon_bars"] <= 0).any():
        raise ValueError("Output contains invalid horizon values.")