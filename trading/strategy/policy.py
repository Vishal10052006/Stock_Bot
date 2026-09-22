"""Prediction and economic policy helpers for the Strategy Engine."""

from __future__ import annotations

import math

from .models import NoTradeReason, StrategyConfig, StrategyDirection


def probability_triplet(prediction: object) -> tuple[float, float, float] | None:
    """Extract canonical LONG/SHORT/NO_EDGE probabilities."""
    probabilities = getattr(prediction, "probabilities", None)
    if probabilities is None:
        return None

    try:
        values = tuple(
            float(probabilities.iloc[0][column])
            for column in ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE")
        )
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return None

    if any(not math.isfinite(value) or value < 0.0 for value in values):
        return None
    if abs(sum(values) - 1.0) > 1e-8:
        return None

    return values


def prediction_evidence(
    prediction: object | None,
    *,
    timestamp,
    symbol: str,
    config: StrategyConfig,
) -> tuple[str | None, float | None, float | None, NoTradeReason | None]:
    """Validate prediction identity/freshness and extract evidence."""
    if prediction is None:
        return None, None, None, None

    prediction_timestamp = getattr(prediction, "timestamp", None)
    prediction_symbol = str(getattr(prediction, "symbol", "")).strip().upper()

    if prediction_timestamp is None or prediction_symbol != symbol.upper():
        return None, None, None, NoTradeReason.INVALID_INPUT

    prediction_timestamp = type(timestamp)(prediction_timestamp)

    if prediction_timestamp.tzinfo is None:
        return None, None, None, NoTradeReason.INVALID_INPUT

    age_seconds = (
        timestamp.to_pydatetime() - prediction_timestamp.to_pydatetime()
    ).total_seconds()

    if age_seconds < 0 or age_seconds > config.prediction_max_age_seconds:
        return None, None, None, NoTradeReason.STALE_PREDICTION

    values = probability_triplet(prediction)
    if values is None:
        return None, None, None, NoTradeReason.INVALID_INPUT

    p_long, p_short, p_no_edge = values
    ordered = sorted(values, reverse=True)
    directional_probability = max(p_long, p_short)
    margin = ordered[0] - ordered[1]

    if p_long >= p_short and p_long >= p_no_edge:
        predicted_class = "LONG_SUCCESS"
    elif p_short >= p_long and p_short >= p_no_edge:
        predicted_class = "SHORT_SUCCESS"
    else:
        predicted_class = "NO_EDGE"

    return predicted_class, directional_probability, margin, None


def prediction_allows_direction(
    predicted_class: str | None,
    direction: StrategyDirection,
    *,
    config: StrategyConfig,
    probability: float | None,
    margin: float | None,
) -> NoTradeReason | None:
    """Return a configured prediction-policy rejection reason."""
    if predicted_class is None:
        return None

    if predicted_class == "NO_EDGE" and config.prediction_min_probability > 0.0:
        return NoTradeReason.NO_EDGE

    if probability is not None and probability < config.prediction_min_probability:
        return NoTradeReason.PREDICTION_EDGE_TOO_WEAK

    if margin is not None and margin < config.prediction_min_margin:
        return NoTradeReason.PREDICTION_EDGE_TOO_WEAK

    if config.require_prediction_direction_alignment:
        expected = (
            "LONG_SUCCESS"
            if direction is StrategyDirection.LONG
            else "SHORT_SUCCESS"
            if direction is StrategyDirection.SHORT
            else None
        )
        if expected is not None and predicted_class != expected:
            return NoTradeReason.SIGNAL_CONFLICT

    return None


def expected_value(
    *,
    win_probability: float,
    expected_reward: float,
    expected_loss: float,
    cost: float = 0.0,
) -> float:
    """Compute EV from explicit decision-time reward/loss assumptions."""
    values = (win_probability, expected_reward, expected_loss, cost)

    if any(not math.isfinite(float(value)) for value in values):
        raise ValueError("expected-value inputs must be finite")
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError("win_probability must be in [0, 1]")
    if min(expected_reward, expected_loss, cost) < 0:
        raise ValueError("reward/loss/cost must be non-negative")

    return (
        win_probability * expected_reward
        - (1.0 - win_probability) * expected_loss
        - cost
    )
