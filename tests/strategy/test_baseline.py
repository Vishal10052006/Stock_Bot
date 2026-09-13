"""
Tests for Phase 8 BaselineStrategy v1.0.
"""

import pandas as pd
import pytest

from trading.strategy import (
    BaselineStrategyConfig,
    StrategyDirection,
    evaluate,
    evaluate_row,
    validate_strategy_output,
)


def make_row(**overrides):
    """Create a deterministic decision-time feature row."""

    row = {
        "timestamp": pd.Timestamp("2026-09-13 10:00:00", tz="Asia/Kolkata"),
        "symbol": "RELIANCE",
        "regime": "TREND_UP",
        "regime_probability": 0.90,
        "vwap_distance_pct": 0.40,
        "rvol_20": 1.40,
        "higher_high": True,
        "higher_low": True,
        "lower_low": False,
        "lower_high": False,
    }

    row.update(overrides)

    return pd.Series(row)


def test_long_setup():
    """All bullish baseline conditions produce LONG."""

    decision = evaluate_row(make_row())

    assert decision.direction is StrategyDirection.LONG


def test_short_setup():
    """All bearish baseline conditions produce SHORT."""

    decision = evaluate_row(
        make_row(
            regime="TREND_DOWN",
            regime_probability=0.90,
            vwap_distance_pct=-0.40,
            rvol_20=1.40,
            higher_high=False,
            higher_low=False,
            lower_low=True,
            lower_high=True,
        )
    )

    assert decision.direction is StrategyDirection.SHORT


def test_range_is_no_trade():
    """RANGE is not a favorable baseline regime."""

    decision = evaluate_row(
        make_row(regime="RANGE")
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_high_volatility_is_no_trade():
    """High-volatility regime is rejected by V1."""

    decision = evaluate_row(
        make_row(regime="HIGH_VOLATILITY")
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_low_volatility_is_no_trade():
    """Low-volatility regime is rejected by V1."""

    decision = evaluate_row(
        make_row(regime="LOW_VOLATILITY")
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_wrong_vwap_for_long_is_no_trade():
    """LONG requires price above VWAP."""

    decision = evaluate_row(
        make_row(vwap_distance_pct=-0.10)
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_wrong_vwap_for_short_is_no_trade():
    """SHORT requires price below VWAP."""

    decision = evaluate_row(
        make_row(
            regime="TREND_DOWN",
            vwap_distance_pct=0.10,
            higher_high=False,
            higher_low=False,
            lower_low=True,
            lower_high=True,
        )
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_low_rvol_is_no_trade():
    """Insufficient participation blocks the trade."""

    decision = evaluate_row(
        make_row(rvol_20=0.99)
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_missing_regime_probability_is_rejected():
    """Missing regime confidence must not silently create a trade."""

    with pytest.raises(
        ValueError,
        match="regime_probability must not be missing",
    ):
        evaluate_row(
            make_row(regime_probability=float("nan"))
        )


def test_custom_rvol_threshold():
    """The explicit configuration controls the RVOL threshold."""

    config = BaselineStrategyConfig(minimum_rvol=1.50)

    decision = evaluate_row(
        make_row(rvol_20=1.40),
        config=config,
    )

    assert decision.direction is StrategyDirection.NO_TRADE


def test_strategy_version_is_recorded():
    """Every decision is tied to a reproducible strategy version."""

    config = BaselineStrategyConfig(
        strategy_version="v1.0-test"
    )

    decision = evaluate_row(
        make_row(),
        config=config,
    )

    assert decision.strategy_version == "v1.0-test"


def test_output_contains_one_decision_per_row():
    """Batch evaluation preserves one decision per observation."""

    features = pd.DataFrame(
        [
            make_row(),
            make_row(
                regime="TREND_DOWN",
                vwap_distance_pct=-0.40,
                higher_high=False,
                higher_low=False,
                lower_low=True,
                lower_high=True,
            ),
            make_row(regime="RANGE"),
        ]
    )

    result = evaluate(features)

    assert len(result) == 3
    assert list(result["direction"]) == [
        "LONG",
        "SHORT",
        "NO_TRADE",
    ]


def test_output_validation():
    """Generated output must satisfy the strategy contract."""

    features = pd.DataFrame([make_row()])

    result = evaluate(features)

    validate_strategy_output(result)


def test_strategy_does_not_use_future_columns():
    """
    Phase 8 must operate solely on decision-time inputs.

    Phase 7 target/outcome columns are deliberately absent.
    """

    features = pd.DataFrame([make_row()])

    result_without_future = evaluate(features)

    features_with_future = features.copy()
    features_with_future["label"] = "LONG_SUCCESS"
    features_with_future["outcome_timestamp"] = pd.Timestamp(
        "2026-09-13 11:00:00",
        tz="Asia/Kolkata",
    )

    result_with_future_columns = evaluate(features_with_future)

    assert result_without_future["direction"].tolist() == (
        result_with_future_columns["direction"].tolist()
    )

def test_missing_structure_is_rejected():
    """Missing structure information must never create a trade."""

    with pytest.raises(
        ValueError,
        match="higher_high must not be missing",
    ):
        evaluate_row(
            make_row(higher_high=pd.NA)
        )


def test_invalid_structure_type_is_rejected():
    """Structure flags must remain boolean decision-time features."""

    with pytest.raises(
        ValueError,
        match="higher_high must be boolean",
    ):
        evaluate_row(
            make_row(higher_high=1.0)
        )
