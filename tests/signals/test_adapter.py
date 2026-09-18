from __future__ import annotations

import pandas as pd

from trading.signals.adapter import (
    build_candidate_from_decision,
)
from trading.signals.models import CandidateDirection
from trading.strategy.models import (
    StrategyDecision,
    StrategyDirection,
)


TIMESTAMP = pd.Timestamp(
    "2026-09-15 10:00:00+05:30"
)


def make_row() -> pd.Series:
    return pd.Series(
        {
            "timestamp": TIMESTAMP,
            "symbol": "RELIANCE",
            "close": 100.0,
            "atr_14": 2.0,
            "swing_low": 97.0,
            "swing_high": 103.0,
            "support_20": 95.0,
            "resistance_20": 105.0,
        }
    )


def make_decision(
    direction: StrategyDirection,
) -> StrategyDecision:
    return StrategyDecision(
        timestamp=TIMESTAMP,
        symbol="RELIANCE",
        direction=direction,
        strategy_version="v1.0",
        rationale="test",
    )


def test_long_decision_becomes_long_candidate() -> None:
    candidate = build_candidate_from_decision(
        make_decision(StrategyDirection.LONG),
        make_row(),
    )

    assert candidate is not None
    assert candidate.direction == CandidateDirection.LONG
    assert candidate.entry_price == 100.0
    assert candidate.stop_price == 97.0


def test_short_decision_becomes_short_candidate() -> None:
    candidate = build_candidate_from_decision(
        make_decision(StrategyDirection.SHORT),
        make_row(),
    )

    assert candidate is not None
    assert candidate.direction == CandidateDirection.SHORT
    assert candidate.entry_price == 100.0
    assert candidate.stop_price == 103.0


def test_no_trade_produces_no_candidate() -> None:
    candidate = build_candidate_from_decision(
        make_decision(StrategyDirection.NO_TRADE),
        make_row(),
    )

    assert candidate is None


def test_timestamp_mismatch_is_rejected() -> None:
    decision = make_decision(
        StrategyDirection.LONG
    )

    row = make_row()
    row["timestamp"] = pd.Timestamp(
        "2026-09-15 10:05:00+05:30"
    )

    import pytest

    with pytest.raises(
        ValueError,
        match="timestamp does not match",
    ):
        build_candidate_from_decision(
            decision,
            row,
        )


def test_symbol_mismatch_is_rejected() -> None:
    decision = make_decision(
        StrategyDirection.LONG
    )

    row = make_row()
    row["symbol"] = "TCS"

    import pytest

    with pytest.raises(
        ValueError,
        match="symbol does not match",
    ):
        build_candidate_from_decision(
            decision,
            row,
        )
