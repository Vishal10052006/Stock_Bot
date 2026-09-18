from __future__ import annotations

import pandas as pd
import pytest

from trading.signals.models import (
    CandidateDirection,
    TradeCandidate,
)
from trading.signals.validation import (
    validate_candidate,
    validate_candidates,
)


def make_candidate(
    *,
    symbol: str = "RELIANCE",
    timestamp: str = "2026-09-15 10:00:00+05:30",
    entry: float = 100.0,
    stop: float = 98.0,
) -> TradeCandidate:
    return TradeCandidate(
        timestamp=pd.Timestamp(timestamp),
        symbol=symbol,
        direction=CandidateDirection.LONG,
        entry_price=entry,
        stop_price=stop,
        policy_version="structure_atr_v1.0",
    )


def test_valid_candidate_passes_validation() -> None:
    validate_candidate(make_candidate())


def test_invalid_object_type_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="TradeCandidate",
    ):
        validate_candidate("not a candidate")  # type: ignore[arg-type]


def test_invalid_candidate_list_type_is_rejected() -> None:
    with pytest.raises(
        TypeError,
        match="list",
    ):
        validate_candidates(())  # type: ignore[arg-type]


def test_empty_candidate_list_is_valid() -> None:
    validate_candidates([])


def test_duplicate_symbol_timestamp_is_rejected() -> None:
    first = make_candidate()
    second = make_candidate()

    with pytest.raises(
        ValueError,
        match="duplicate candidate",
    ):
        validate_candidates([first, second])


def test_same_timestamp_different_symbols_is_valid() -> None:
    first = make_candidate(symbol="RELIANCE")
    second = make_candidate(symbol="TCS")

    validate_candidates([first, second])


def test_non_positive_stop_distance_is_rejected() -> None:
    candidate = make_candidate()

    # The dataclass itself protects this invariant, so validation is
    # tested through an intentionally bypassed frozen instance.
    object.__setattr__(
        candidate,
        "stop_price",
        100.0,
    )

    with pytest.raises(
        ValueError,
        match="stop distance",
    ):
        validate_candidate(candidate)
