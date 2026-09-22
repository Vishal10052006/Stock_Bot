"""Tests for the Strategy -> TradeCandidate boundary."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.strategy import (
    StrategyDirection,
    StrategyEngine,
    StrategyInput,
    build_candidate_from_strategy,
)


def make_row() -> pd.Series:
    """Create a causal candidate-compatible decision row."""
    return pd.Series(
        {
            "timestamp": pd.Timestamp("2026-09-21 10:25:00+00:00"),
            "symbol": "RELIANCE",
            "close": 100.0,
            "atr_14": 2.0,
            "swing_low": 96.0,
            "swing_high": 104.0,
            "vwap_distance_pct": 0.5,
            "rvol_20": 1.4,
            "higher_high": True,
            "higher_low": True,
            "lower_low": False,
            "lower_high": False,
            "regime": "TREND_UP",
            "regime_probability": 0.90,
        }
    )


def make_long_decision():
    """Create the authoritative LONG strategy decision."""
    row = make_row()
    decision_input = {
        "timestamp": row["timestamp"],
        "symbol": row["symbol"],
        "decision_features": {
            "vwap_distance_pct": row["vwap_distance_pct"],
            "rvol_20": row["rvol_20"],
            "higher_high": row["higher_high"],
            "higher_low": row["higher_low"],
            "lower_low": row["lower_low"],
            "lower_high": row["lower_high"],
        },
        "regime": row["regime"],
        "regime_probability": row["regime_probability"],
    }

    decision, _trace = StrategyEngine().decide(
        StrategyInput(**decision_input)
    )
    return decision


def test_strategy_can_materialize_causal_candidate() -> None:
    """LONG strategy direction becomes a valid research candidate."""
    candidate = build_candidate_from_strategy(
        make_long_decision(),
        make_row(),
    )

    assert candidate.direction.value == "LONG"
    assert candidate.entry_price == 100.0
    assert candidate.stop_price < candidate.entry_price
    assert candidate.policy_version == "structure_atr_v1.0"


def test_no_trade_cannot_materialize_candidate() -> None:
    """NO_TRADE remains a hard boundary."""
    row = make_row()
    row["regime"] = "RANGE"

    decision, _trace = StrategyEngine().decide(
        StrategyInput(
            timestamp=row["timestamp"],
            symbol=row["symbol"],
            decision_features={
                "vwap_distance_pct": row["vwap_distance_pct"],
                "rvol_20": row["rvol_20"],
                "higher_high": row["higher_high"],
                "higher_low": row["higher_low"],
                "lower_low": row["lower_low"],
                "lower_high": row["lower_high"],
            },
            regime="RANGE",
            regime_probability=0.90,
        )
    )

    assert decision.direction is StrategyDirection.NO_TRADE

    with pytest.raises(ValueError, match="NO_TRADE"):
        build_candidate_from_strategy(decision, row)
