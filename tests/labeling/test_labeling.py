"""
Comprehensive tests for Phase 7 prediction-target labeling.

These tests verify:
    - LONG target outcomes
    - LONG stop outcomes
    - SHORT target outcomes
    - SHORT stop outcomes
    - ambiguous OHLC bars
    - horizon expiry
    - insufficient future data
    - multiple symbols
    - timestamp causality
    - invalid inputs
    - batch labeling
"""

from __future__ import annotations

import pandas as pd
import pytest

from ml.labeling import (
    LabelingConfig,
    PredictionLabel,
    TradeCandidate,
    TradeDirection,
    label_candidate,
    label_candidates,
    validate_candidate_against_candles,
    validate_labeling_output,
)
from ml.labeling import label_decision


def make_candles(
    highs: list[float],
    lows: list[float],
    symbol: str = "RELIANCE",
    start: str = "2026-09-13 10:00",
) -> pd.DataFrame:
    """Create deterministic 5-minute OHLC test candles."""

    timestamps = pd.date_range(
        start=start,
        periods=len(highs),
        freq="5min",
    )

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": [symbol] * len(timestamps),
            "open": [100.0] * len(timestamps),
            "high": highs,
            "low": lows,
            "close": [100.0] * len(timestamps),
        }
    )


def make_long_candidate(
    timestamp: str = "2026-09-13 10:00",
) -> TradeCandidate:
    """Create a standard LONG candidate."""

    return TradeCandidate(
        timestamp=pd.Timestamp(timestamp),
        symbol="RELIANCE",
        direction=TradeDirection.LONG,
        entry_price=100.0,
        stop_price=98.0,
    )


def make_short_candidate(
    timestamp: str = "2026-09-13 10:00",
) -> TradeCandidate:
    """Create a standard SHORT candidate."""

    return TradeCandidate(
        timestamp=pd.Timestamp(timestamp),
        symbol="RELIANCE",
        direction=TradeDirection.SHORT,
        entry_price=100.0,
        stop_price=102.0,
    )


def test_long_target_hit():
    """LONG should succeed when its target is reached first."""

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.LONG_SUCCESS
    assert outcome.target_price == pytest.approx(103.0)
    assert outcome.outcome_bars == 3
    assert outcome.outcome_reason == "TARGET_HIT"


def test_long_stop_hit():
    """LONG should become NO_EDGE when its stop is reached first."""

    candles = make_candles(
        highs=[100.5, 100.8],
        lows=[99.5, 97.5],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_bars == 1
    assert outcome.outcome_reason == "STOP_HIT"


def test_short_target_hit():
    """SHORT should succeed when its target is reached first."""

    candles = make_candles(
        highs=[100.5, 100.2, 99.0, 96.5],
        lows=[99.5, 99.0, 98.5, 96.5],
    )

    outcome = label_candidate(
        candles,
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.SHORT_SUCCESS
    assert outcome.target_price == pytest.approx(97.0)
    assert outcome.outcome_bars == 3
    assert outcome.outcome_reason == "TARGET_HIT"


def test_short_stop_hit():
    """SHORT should become NO_EDGE when its stop is reached first."""

    candles = make_candles(
        highs=[100.5, 102.5],
        lows=[99.5, 100.0],
    )

    outcome = label_candidate(
        candles,
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_bars == 1
    assert outcome.outcome_reason == "STOP_HIT"


def test_same_candle_target_and_stop_is_ambiguous():
    """
    OHLC cannot establish whether target or stop happened first.

    The conservative policy is therefore NO_EDGE.
    """

    candles = make_candles(
        highs=[100.5, 103.5],
        lows=[99.5, 97.5],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_reason == (
        "AMBIGUOUS_TARGET_AND_STOP_SAME_BAR"
    )


def test_short_same_candle_target_and_stop_is_ambiguous():
    """SHORT ambiguity must also resolve to NO_EDGE."""

    candles = make_candles(
        highs=[100.5, 102.5],
        lows=[99.5, 96.5],
    )

    outcome = label_candidate(
        candles,
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_reason == (
        "AMBIGUOUS_TARGET_AND_STOP_SAME_BAR"
    )


def test_horizon_expiry():
    """No barrier hit within the configured horizon becomes NO_EDGE."""

    candles = make_candles(
        highs=[100.5] * 13,
        lows=[99.5] * 13,
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_bars == 12
    assert outcome.outcome_reason == "HORIZON_EXPIRED"


def test_only_configured_horizon_is_evaluated():
    """A target after the horizon must not affect the label."""

    candles = make_candles(
        highs=[100.5] * 13 + [103.5],
        lows=[99.5] * 14,
    )

    config = LabelingConfig(horizon_bars=12)

    outcome = label_candidate(
        candles,
        make_long_candidate(),
        config,
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_bars == 12
    assert outcome.outcome_reason == "HORIZON_EXPIRED"


def test_insufficient_future_bars():
    """Missing future bars should be explicitly reported."""

    candles = make_candles(
        highs=[100.5, 101.0],
        lows=[99.5, 99.8],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_reason == "INSUFFICIENT_FUTURE_BARS"


def test_candidate_without_future_data():
    """
    If the candidate is the final candle, the engine must not
    manufacture an outcome from the decision candle itself.
    """

    candles = make_candles(
        highs=[100.5],
        lows=[99.5],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_timestamp is None
    assert outcome.outcome_bars is None
    assert outcome.outcome_reason == "INSUFFICIENT_FUTURE_BARS"


def test_decision_candle_is_never_used():
    """
    A barrier touched on the decision candle must not create a
    successful label.
    """

    candles = make_candles(
        highs=[103.5, 100.5],
        lows=[97.5, 99.5],
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_timestamp is None
    assert outcome.outcome_reason == "INSUFFICIENT_FUTURE_BARS"


def test_multiple_symbols_are_isolated():
    """Future candles from another symbol must never affect a candidate."""

    timestamps = pd.date_range(
        "2026-09-13 10:00",
        periods=3,
        freq="5min",
    )

    candles = pd.DataFrame(
        {
            "timestamp": list(timestamps) * 2,
            "symbol": [
                "RELIANCE",
                "RELIANCE",
                "RELIANCE",
                "TCS",
                "TCS",
                "TCS",
            ],
            "open": [100.0] * 6,
            "high": [
                100.5,
                100.5,
                100.5,
                200.0,
                210.0,
                220.0,
            ],
            "low": [
                99.5,
                99.5,
                99.5,
                199.0,
                209.0,
                219.0,
            ],
            "close": [100.0] * 6,
        }
    )

    outcome = label_candidate(
        candles,
        make_long_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.symbol == "RELIANCE"


def test_batch_labeling():
    """Multiple candidates should produce one auditable row each."""

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    candidates = [
        make_long_candidate(),
        make_short_candidate(),
    ]

    output = label_candidates(
        candles,
        candidates,
    )

    assert len(output) == 2
    assert set(output["label"]) == {
        "LONG_SUCCESS",
        "NO_EDGE",
    }


def test_empty_candidate_batch():
    """An empty candidate collection should return the defined schema."""

    candles = make_candles(
        highs=[100.5],
        lows=[99.5],
    )

    output = label_candidates(
        candles,
        [],
    )

    assert output.empty
    assert "label" in output.columns
    assert "target_price" in output.columns


def test_missing_candle_column_is_rejected():
    """Required OHLC columns must be present."""

    candles = make_candles(
        highs=[100.5],
        lows=[99.5],
    ).drop(columns=["high"])

    with pytest.raises(ValueError, match="required columns"):
        label_candidate(
            candles,
            make_long_candidate(),
        )


def test_invalid_candle_range_is_rejected():
    """A candle cannot have high below low."""

    candles = make_candles(
        highs=[99.0],
        lows=[101.0],
    )

    with pytest.raises(ValueError, match="high cannot be below"):
        label_candidate(
            candles,
            make_long_candidate(),
        )


def test_invalid_candidate_is_rejected():
    """LONG candidate cannot have a stop above entry."""

    with pytest.raises(ValueError, match="LONG stop_price"):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-13 10:00"),
            symbol="RELIANCE",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            stop_price=102.0,
        )


def test_short_invalid_candidate_is_rejected():
    """SHORT candidate cannot have a stop below entry."""

    with pytest.raises(ValueError, match="SHORT stop_price"):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-13 10:00"),
            symbol="RELIANCE",
            direction=TradeDirection.SHORT,
            entry_price=100.0,
            stop_price=98.0,
        )


def test_invalid_config_is_rejected():
    """Invalid R multiple and horizon must fail immediately."""

    with pytest.raises(ValueError):
        LabelingConfig(target_r_multiple=0)

    with pytest.raises(ValueError):
        LabelingConfig(horizon_bars=0)


def test_candidate_validation_requires_future_data():
    """Validation should reject a candidate without future candles."""

    candles = make_candles(
        highs=[100.5],
        lows=[99.5],
    )

    with pytest.raises(
        ValueError,
        match="no future candles",
    ):
        validate_candidate_against_candles(
            candles,
            make_long_candidate(),
        )


def test_labeling_output_validation():
    """Generated output should satisfy the labeling schema."""

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    output = label_candidates(
        candles,
        [make_long_candidate()],
    )

    validate_labeling_output(output)


def test_future_outcome_timestamp_is_after_decision_timestamp():
    """Outcome timestamp must always be strictly after decision time."""

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    candidate = make_long_candidate()

    outcome = label_candidate(
        candles,
        candidate,
    )

    assert outcome.outcome_timestamp > candidate.timestamp


def test_target_distance_is_exactly_1_5_r():
    """Target distance must equal the configured 1.5R."""

    candles = make_candles(
        highs=[100.5, 101.0],
        lows=[99.5, 99.8],
    )

    candidate = make_long_candidate()

    outcome = label_candidate(
        candles,
        candidate,
    )

    risk = abs(
        candidate.entry_price - candidate.stop_price
    )

    expected_target = (
        candidate.entry_price + 1.5 * risk
    )

    assert outcome.target_price == pytest.approx(
        expected_target
    )

def test_decision_label_long_success():
    """LONG success should become the decision-level target."""

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    outcome = label_decision(
        candles,
        make_long_candidate(),
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.LONG_SUCCESS
    assert outcome.outcome_bars == 3


def test_decision_label_short_success():
    """SHORT success should become the decision-level target."""

    candles = make_candles(
        highs=[100.5, 100.2, 99.0, 96.5],
        lows=[99.5, 99.0, 98.5, 96.5],
    )

    outcome = label_decision(
        candles,
        make_long_candidate(),
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.SHORT_SUCCESS
    assert outcome.outcome_bars == 3


def test_decision_label_no_edge_when_neither_succeeds():
    """No successful direction should produce NO_EDGE."""

    candles = make_candles(
        highs=[100.5] * 13,
        lows=[99.5] * 13,
    )

    outcome = label_decision(
        candles,
        make_long_candidate(),
        make_short_candidate(),
    )

    assert outcome.label == PredictionLabel.NO_EDGE
    assert outcome.outcome_reason == "NO_DIRECTIONAL_SUCCESS"


def test_decision_label_requires_same_timestamp():
    """Both directional candidates must represent one decision."""

    long_candidate = make_long_candidate(
        timestamp="2026-09-13 10:00"
    )

    short_candidate = make_short_candidate(
        timestamp="2026-09-13 10:05"
    )

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 103.5],
        lows=[99.5, 99.8, 100.5, 101.5],
    )

    with pytest.raises(
        ValueError,
        match="same timestamp",
    ):
        label_decision(
            candles,
            long_candidate,
            short_candidate,
        )


def test_decision_label_rejects_wrong_direction():
    """The LONG slot must actually contain a LONG candidate."""

    candles = make_candles(
        highs=[100.5, 101.0],
        lows=[99.5, 99.8],
    )

    with pytest.raises(
        ValueError,
        match="long_candidate must have LONG direction",
    ):
        label_decision(
            candles,
            make_short_candidate(),
            make_short_candidate(),
        )

def test_decision_label_both_successes_earlier_direction_wins():
    """When both directions eventually succeed, the earlier one wins."""

    long_candidate = TradeCandidate(
        timestamp=pd.Timestamp("2026-09-13 10:00"),
        symbol="RELIANCE",
        direction=TradeDirection.LONG,
        entry_price=100.0,
        stop_price=99.0,
    )

    short_candidate = TradeCandidate(
        timestamp=pd.Timestamp("2026-09-13 10:00"),
        symbol="RELIANCE",
        direction=TradeDirection.SHORT,
        entry_price=100.0,
        stop_price=105.0,
    )

    candles = make_candles(
        highs=[100.5, 101.0, 102.0, 100.0],
        lows=[99.5, 99.5, 99.5, 92.0],
    )

    outcome = label_decision(
        candles,
        long_candidate,
        short_candidate,
    )

    assert outcome.label == PredictionLabel.LONG_SUCCESS
    assert outcome.outcome_bars == 2
    assert outcome.outcome_reason == "LONG_SUCCESS_BEFORE_SHORT"

    assert (
        outcome.long_outcome.label
        == PredictionLabel.LONG_SUCCESS
    )

    assert (
        outcome.short_outcome.label
        == PredictionLabel.SHORT_SUCCESS
    )

    assert outcome.long_outcome.outcome_bars == 2
    assert outcome.short_outcome.outcome_bars == 3