from __future__ import annotations

import pandas as pd
import pytest

from ml.labeling.models import (
    TradeDirection,
)

from trading.signals.labeling_adapter import (
    to_labeling_candidate,
)
from trading.signals.models import (
    CandidateDirection,
    TradeCandidate,
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


def test_long_candidate_converts_to_phase7_long() -> None:
    source = make_candidate(
        CandidateDirection.LONG
    )

    result = to_labeling_candidate(source)

    assert result.timestamp == source.timestamp
    assert result.symbol == source.symbol
    assert result.direction == TradeDirection.LONG
    assert result.entry_price == 100.0
    assert result.stop_price == 98.0


def test_short_candidate_converts_to_phase7_short() -> None:
    source = make_candidate(
        CandidateDirection.SHORT
    )

    result = to_labeling_candidate(source)

    assert result.timestamp == source.timestamp
    assert result.symbol == source.symbol
    assert result.direction == TradeDirection.SHORT
    assert result.entry_price == 100.0
    assert result.stop_price == 102.0


def test_policy_version_is_not_passed_to_phase7() -> None:
    source = make_candidate(
        CandidateDirection.LONG
    )

    result = to_labeling_candidate(source)

    assert not hasattr(result, "policy_version")


def test_wrong_type_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="trading.signals TradeCandidate",
    ):
        to_labeling_candidate("invalid")  # type: ignore[arg-type]
