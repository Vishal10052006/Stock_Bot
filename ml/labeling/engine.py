"""
Outcome engine for Phase 7 prediction-target labeling.

The engine evaluates only candles strictly after the decision timestamp.
Future candles are used exclusively to determine the research outcome.
They must never be used to construct decision-time features.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from .models import (
    LabelingConfig,
    LabelingOutcome,
    PredictionLabel,
    TradeCandidate,
    TradeDirection,
)


_REQUIRED_COLUMNS = {
    "timestamp",
    "symbol",
    "open",
    "high",
    "low",
    "close",
}


def _calculate_target(
    candidate: TradeCandidate,
    config: LabelingConfig,
) -> float:
    """Calculate the target price from the candidate's initial R."""

    risk_distance = abs(
        candidate.entry_price - candidate.stop_price
    )

    if candidate.direction == TradeDirection.LONG:
        return (
            candidate.entry_price
            + config.target_r_multiple * risk_distance
        )

    return (
        candidate.entry_price
        - config.target_r_multiple * risk_distance
    )


def _validate_candles(candles: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and normalize the candle input.

    The function does not alter the original DataFrame.
    """

    if not isinstance(candles, pd.DataFrame):
        raise TypeError("candles must be a pandas DataFrame.")

    missing = _REQUIRED_COLUMNS.difference(candles.columns)

    if missing:
        raise ValueError(
            f"candles is missing required columns: {sorted(missing)}"
        )

    result = candles.copy()

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        errors="raise",
    )

    if result["timestamp"].isna().any():
        raise ValueError("candles contains invalid timestamps.")

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="raise",
        )

    if result[numeric_columns].isna().any().any():
        raise ValueError("candles contains missing OHLC values.")

    if (result["high"] < result["low"]).any():
        raise ValueError("candle high cannot be below candle low.")

    if (result["symbol"].astype(str).str.strip() == "").any():
        raise ValueError("candles contains an empty symbol.")

    return result.sort_values(
        ["symbol", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)


def _make_outcome(
    candidate: TradeCandidate,
    target_price: float,
    config: LabelingConfig,
    label: PredictionLabel,
    outcome_timestamp: pd.Timestamp | None,
    outcome_bars: int | None,
    outcome_reason: str,
) -> LabelingOutcome:
    """Construct the standardized labeling result."""

    return LabelingOutcome(
        timestamp=candidate.timestamp,
        symbol=candidate.symbol,
        label=label,
        entry_price=candidate.entry_price,
        stop_price=candidate.stop_price,
        target_price=target_price,
        horizon_bars=config.horizon_bars,
        outcome_timestamp=outcome_timestamp,
        outcome_bars=outcome_bars,
        outcome_reason=outcome_reason,
    )


def label_candidate(
    candles: pd.DataFrame,
    candidate: TradeCandidate,
    config: LabelingConfig | None = None,
) -> LabelingOutcome:
    """
    Label one trade candidate using future candles.

    Important causality rule:
        Only candles with timestamp strictly greater than the
        candidate timestamp are eligible for outcome evaluation.

    Returns:
        LabelingOutcome containing the target and realized research
        outcome.
    """

    if config is None:
        config = LabelingConfig()

    validated = _validate_candles(candles)

    target_price = _calculate_target(candidate, config)

    symbol_candles = validated[
        validated["symbol"].astype(str) == candidate.symbol
    ]

    available_future = symbol_candles[
        symbol_candles["timestamp"] > candidate.timestamp
    ]

    future = available_future.head(config.horizon_bars)

    if future.empty:
        return _make_outcome(
            candidate=candidate,
            target_price=target_price,
            config=config,
            label=PredictionLabel.NO_EDGE,
            outcome_timestamp=None,
            outcome_bars=None,
            outcome_reason="INSUFFICIENT_FUTURE_BARS",
        )

    for bar_number, (_, candle) in enumerate(
        future.iterrows(),
        start=1,
    ):
        high = float(candle["high"])
        low = float(candle["low"])

        if candidate.direction == TradeDirection.LONG:
            target_hit = high >= target_price
            stop_hit = low <= candidate.stop_price

            if target_hit and stop_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.NO_EDGE,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="AMBIGUOUS_TARGET_AND_STOP_SAME_BAR",
                )

            if target_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.LONG_SUCCESS,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="TARGET_HIT",
                )

            if stop_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.NO_EDGE,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="STOP_HIT",
                )

        else:
            target_hit = low <= target_price
            stop_hit = high >= candidate.stop_price

            if target_hit and stop_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.NO_EDGE,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="AMBIGUOUS_TARGET_AND_STOP_SAME_BAR",
                )

            if target_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.SHORT_SUCCESS,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="TARGET_HIT",
                )

            if stop_hit:
                return _make_outcome(
                    candidate=candidate,
                    target_price=target_price,
                    config=config,
                    label=PredictionLabel.NO_EDGE,
                    outcome_timestamp=candle["timestamp"],
                    outcome_bars=bar_number,
                    outcome_reason="STOP_HIT",
                )

    if len(available_future) < config.horizon_bars:
        return _make_outcome(
            candidate=candidate,
            target_price=target_price,
            config=config,
            label=PredictionLabel.NO_EDGE,
            outcome_timestamp=None,
            outcome_bars=None,
            outcome_reason="INSUFFICIENT_FUTURE_BARS",
        )

    return _make_outcome(
        candidate=candidate,
        target_price=target_price,
        config=config,
        label=PredictionLabel.NO_EDGE,
        outcome_timestamp=future.iloc[-1]["timestamp"],
        outcome_bars=len(future),
        outcome_reason="HORIZON_EXPIRED",
    )


def label_candidates(
    candles: pd.DataFrame,
    candidates: Iterable[TradeCandidate],
    config: LabelingConfig | None = None,
) -> pd.DataFrame:
    """
    Label multiple candidates and return an auditable DataFrame.
    """

    if config is None:
        config = LabelingConfig()

    outcomes = [
        label_candidate(
            candles=candles,
            candidate=candidate,
            config=config,
        )
        for candidate in candidates
    ]

    if not outcomes:
        return pd.DataFrame(
            columns=[
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
            ]
        )

    return pd.DataFrame(
        [
            {
                "timestamp": outcome.timestamp,
                "symbol": outcome.symbol,
                "label": outcome.label.value,
                "entry_price": outcome.entry_price,
                "stop_price": outcome.stop_price,
                "target_price": outcome.target_price,
                "horizon_bars": outcome.horizon_bars,
                "outcome_timestamp": outcome.outcome_timestamp,
                "outcome_bars": outcome.outcome_bars,
                "outcome_reason": outcome.outcome_reason,
            }
            for outcome in outcomes
        ]
    )
