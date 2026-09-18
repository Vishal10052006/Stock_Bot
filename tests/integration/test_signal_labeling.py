from __future__ import annotations

import pandas as pd

from ml.labeling import (
    LabelingConfig,
    PredictionLabel,
    label_decision,
)

from trading.signals import (
    CandidateDirection,
    TradeCandidate,
)
from trading.signals.labeling_adapter import (
    to_labeling_candidate,
)


TIMESTAMP = pd.Timestamp(
    "2026-09-15 10:00:00+05:30"
)


def make_candidate(
    direction: CandidateDirection,
) -> TradeCandidate:
    if direction == CandidateDirection.LONG:
        stop = 98.0
    else:
        stop = 102.0

    return TradeCandidate(
        timestamp=TIMESTAMP,
        symbol="RELIANCE",
        direction=direction,
        entry_price=100.0,
        stop_price=stop,
        policy_version="structure_atr_v1.0",
    )


def make_candles(
    rows: list[tuple[str, float, float, float, float]],
) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
        ],
    ).assign(symbol="RELIANCE")


def label_candidates(
    candles: pd.DataFrame,
):
    long_candidate = to_labeling_candidate(
        make_candidate(CandidateDirection.LONG)
    )

    short_candidate = to_labeling_candidate(
        make_candidate(CandidateDirection.SHORT)
    )

    return label_decision(
        candles=candles,
        long_candidate=long_candidate,
        short_candidate=short_candidate,
        config=LabelingConfig(),
    )


def test_long_success_flows_through_candidate_to_phase7() -> None:
    candles = make_candles(
        [
            (
                "2026-09-15 10:00:00+05:30",
                100.0,
                100.5,
                99.5,
                100.0,
            ),
            (
                "2026-09-15 10:05:00+05:30",
                100.0,
                101.0,
                99.5,
                100.5,
            ),
            (
                "2026-09-15 10:10:00+05:30",
                100.5,
                104.0,
                100.0,
                103.5,
            ),
        ]
    )

    result = label_candidates(candles)

    assert result.label == PredictionLabel.LONG_SUCCESS
    assert result.timestamp == TIMESTAMP
    assert result.symbol == "RELIANCE"
    assert result.outcome_bars == 2


def test_short_success_flows_through_candidate_to_phase7() -> None:
    candles = make_candles(
        [
            (
                "2026-09-15 10:00:00+05:30",
                100.0,
                100.5,
                99.5,
                100.0,
            ),
            (
                "2026-09-15 10:05:00+05:30",
                100.0,
                100.5,
                99.0,
                99.5,
            ),
            (
                "2026-09-15 10:10:00+05:30",
                99.5,
                99.5,
                96.0,
                96.5,
            ),
        ]
    )

    result = label_candidates(candles)

    assert result.label == PredictionLabel.SHORT_SUCCESS
    assert result.timestamp == TIMESTAMP
    assert result.symbol == "RELIANCE"
    assert result.outcome_bars == 2


def test_neither_direction_success_is_no_edge() -> None:
    candles = make_candles(
        [
            (
                "2026-09-15 10:00:00+05:30",
                100.0,
                100.5,
                99.5,
                100.0,
            ),
            (
                "2026-09-15 10:05:00+05:30",
                100.0,
                101.0,
                99.0,
                100.0,
            ),
            (
                "2026-09-15 10:10:00+05:30",
                100.0,
                101.0,
                99.0,
                100.0,
            ),
        ]
    )

    result = label_candidates(candles)

    assert result.label == PredictionLabel.NO_EDGE


def test_future_candles_are_not_used_as_decision_input() -> None:
    candles = make_candles(
        [
            (
                "2026-09-15 10:00:00+05:30",
                100.0,
                100.5,
                99.5,
                100.0,
            ),
            (
                "2026-09-15 10:05:00+05:30",
                100.0,
                101.0,
                99.5,
                100.5,
            ),
            (
                "2026-09-15 10:10:00+05:30",
                100.5,
                104.0,
                100.0,
                103.5,
            ),
        ]
    )

    long_candidate = make_candidate(
        CandidateDirection.LONG
    )

    # Candidate construction itself contains no future candle data.
    assert long_candidate.timestamp == TIMESTAMP
    assert long_candidate.entry_price == 100.0
    assert long_candidate.stop_price == 98.0

    result = label_candidates(candles)

    # Future data is only consumed by Phase 7.
    assert result.label == PredictionLabel.LONG_SUCCESS
