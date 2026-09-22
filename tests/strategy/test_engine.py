"""Focused tests for the S0-S28 Strategy Engine boundary."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.strategy import (
    NoTradeReason,
    StrategyConfig,
    StrategyDirection,
    StrategyEngine,
    StrategyInput,
    validate_strategy_decision,
)


def make_features(**overrides: object) -> dict[str, object]:
    """Create a valid decision-time feature mapping."""
    values: dict[str, object] = {
        "vwap_distance_pct": 0.5,
        "rvol_20": 1.4,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }
    values.update(overrides)
    return values


def make_input(**overrides: object) -> StrategyInput:
    """Create a deterministic LONG StrategyInput."""
    defaults = {
        "timestamp": pd.Timestamp(
            "2026-09-20 10:25:00+05:30"
        ),
        "symbol": "RELIANCE",
        "decision_features": make_features(),
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "versions": {
            "feature": "feature-v1.0",
            "market": "market-v1.0",
            "analysis": "analysis-v1.0",
            "research": "research-v1.0",
        },
    }
    defaults.update(overrides)
    return StrategyInput(**defaults)


def test_engine_reproduces_baseline_long() -> None:
    """The new engine preserves the Phase 8 baseline setup."""
    decision, trace = StrategyEngine().decide(
        make_input()
    )

    assert decision.direction is StrategyDirection.LONG
    assert decision.strategy_version == "STRAT-v1.0"
    assert trace.failed_reasons == ()
    validate_strategy_decision(decision)


def test_range_is_structured_no_trade() -> None:
    """Range regime is a first-class strategy rejection."""
    decision, trace = StrategyEngine().decide(
        make_input(regime="RANGE")
    )

    assert decision.direction is StrategyDirection.NO_TRADE
    assert decision.primary_reason is NoTradeReason.REGIME_NOT_ELIGIBLE
    assert trace.failed_reasons == (
        NoTradeReason.REGIME_NOT_ELIGIBLE,
    )


def test_low_regime_confidence_is_no_trade() -> None:
    decision, _ = StrategyEngine().decide(
        make_input(regime_probability=0.40)
    )

    assert (
        decision.primary_reason
        is NoTradeReason.REGIME_CONFIDENCE_TOO_LOW
    )


def test_missing_baseline_feature_fails_closed() -> None:
    features = make_features()
    features.pop("higher_high")

    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        StrategyEngine().decide(
            make_input(
                decision_features=features
            )
        )


def test_prediction_alignment_can_be_enabled() -> None:
    class FakePrediction:
        """Minimal prediction fixture matching PredictionContext semantics."""

        timestamp = pd.Timestamp(
            "2026-09-20 10:25:00+05:30"
        )
        symbol = "RELIANCE"
        model_version = "model-v1"
        probabilities = pd.DataFrame(
            [[0.10, 0.80, 0.10]],
            columns=[
                "LONG_SUCCESS",
                "SHORT_SUCCESS",
                "NO_EDGE",
            ],
        )

    config = StrategyConfig(
        require_prediction_direction_alignment=True
    )

    decision, _ = StrategyEngine(
        config
    ).decide(
        make_input(
            prediction=FakePrediction()
        )
    )

    assert decision.direction is StrategyDirection.NO_TRADE
    assert (
        decision.primary_reason
        is NoTradeReason.SIGNAL_CONFLICT
    )


def test_probability_threshold_is_configurable() -> None:
    class FakePrediction:
        """Prediction fixture with insufficient directional edge."""

        timestamp = pd.Timestamp(
            "2026-09-20 10:25:00+05:30"
        )
        symbol = "RELIANCE"
        model_version = "model-v1"
        probabilities = pd.DataFrame(
            [[0.58, 0.22, 0.20]],
            columns=[
                "LONG_SUCCESS",
                "SHORT_SUCCESS",
                "NO_EDGE",
            ],
        )

    decision, _ = StrategyEngine(
        StrategyConfig(
            prediction_min_probability=0.60
        )
    ).decide(
        make_input(
            prediction=FakePrediction()
        )
    )

    assert decision.direction is StrategyDirection.NO_TRADE
    assert (
        decision.primary_reason
        is NoTradeReason.PREDICTION_EDGE_TOO_WEAK
    )


def test_future_prediction_is_rejected_before_strategy() -> None:
    class FakePrediction:
        """Prediction intentionally from the future."""

        timestamp = pd.Timestamp(
            "2026-09-20 10:30:00+05:30"
        )
        symbol = "RELIANCE"
        model_version = "model-v1"
        probabilities = pd.DataFrame(
            [[0.80, 0.10, 0.10]],
            columns=[
                "LONG_SUCCESS",
                "SHORT_SUCCESS",
                "NO_EDGE",
            ],
        )

    with pytest.raises(
        ValueError,
        match="future",
    ):
        StrategyEngine().decide(
            make_input(
                prediction=FakePrediction()
            )
        )
