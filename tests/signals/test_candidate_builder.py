from __future__ import annotations

import pandas as pd
import pytest

from trading.signals.candidate import build_candidate
from trading.signals.models import (
    CandidateConfig,
    CandidateDirection,
)


TIMESTAMP = pd.Timestamp(
    "2026-09-15 10:00:00+05:30"
)


def make_row(**overrides: object) -> pd.Series:
    values = {
        "timestamp": TIMESTAMP,
        "symbol": "RELIANCE",
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 96.0,
        "swing_high": 104.0,
        "support_20": 95.0,
        "resistance_20": 105.0,
    }

    values.update(overrides)

    return pd.Series(values)


def test_long_uses_swing_and_atr_constraint() -> None:
    candidate = build_candidate(
        make_row(
            swing_low=97.0,
            atr_14=2.0,
        ),
        CandidateDirection.LONG,
    )

    # ATR stop = 100 - 1.5 * 2 = 97.
    assert candidate.entry_price == 100.0
    assert candidate.stop_price == 97.0


def test_long_structure_closer_than_atr_wins() -> None:
    candidate = build_candidate(
        make_row(
            swing_low=98.0,
            atr_14=2.0,
        ),
        CandidateDirection.LONG,
    )

    # max(98, 97) = 98
    assert candidate.stop_price == 98.0


def test_long_atr_constraint_closer_than_structure_wins() -> None:
    candidate = build_candidate(
        make_row(
            swing_low=94.0,
            atr_14=2.0,
        ),
        CandidateDirection.LONG,
    )

    # max(94, 97) = 97
    assert candidate.stop_price == 97.0


def test_short_uses_swing_and_atr_constraint() -> None:
    candidate = build_candidate(
        make_row(
            swing_high=103.0,
            atr_14=2.0,
        ),
        CandidateDirection.SHORT,
    )

    # ATR stop = 100 + 1.5 * 2 = 103.
    assert candidate.entry_price == 100.0
    assert candidate.stop_price == 103.0


def test_short_structure_closer_than_atr_wins() -> None:
    candidate = build_candidate(
        make_row(
            swing_high=102.0,
            atr_14=2.0,
        ),
        CandidateDirection.SHORT,
    )

    # min(102, 103) = 102
    assert candidate.stop_price == 102.0


def test_short_atr_constraint_closer_than_structure_wins() -> None:
    candidate = build_candidate(
        make_row(
            swing_high=106.0,
            atr_14=2.0,
        ),
        CandidateDirection.SHORT,
    )

    # min(106, 103) = 103
    assert candidate.stop_price == 103.0


def test_long_falls_back_to_support_when_swing_missing() -> None:
    candidate = build_candidate(
        make_row(
            swing_low=float("nan"),
            support_20=96.0,
            atr_14=2.0,
        ),
        CandidateDirection.LONG,
    )

    assert candidate.stop_price == 97.0


def test_short_falls_back_to_resistance_when_swing_missing() -> None:
    candidate = build_candidate(
        make_row(
            swing_high=float("nan"),
            resistance_20=104.0,
            atr_14=2.0,
        ),
        CandidateDirection.SHORT,
    )

    assert candidate.stop_price == 103.0


def test_long_rejects_structure_on_wrong_side() -> None:
    with pytest.raises(
        ValueError,
        match="LONG structural stop",
    ):
        build_candidate(
            make_row(
                swing_low=101.0,
                support_20=101.0,
            ),
            CandidateDirection.LONG,
        )


def test_short_rejects_structure_on_wrong_side() -> None:
    with pytest.raises(
        ValueError,
        match="SHORT structural stop",
    ):
        build_candidate(
            make_row(
                swing_high=99.0,
                resistance_20=99.0,
            ),
            CandidateDirection.SHORT,
        )


def test_missing_atr_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="atr_14",
    ):
        build_candidate(
            make_row(atr_14=float("nan")),
            CandidateDirection.LONG,
        )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_candidate(
            make_row(
                timestamp=pd.Timestamp(
                    "2026-09-15 10:00:00"
                )
            ),
            CandidateDirection.LONG,
        )


def test_candidate_policy_version_is_preserved() -> None:
    config = CandidateConfig(
        policy_version="structure_atr_v1.0"
    )

    candidate = build_candidate(
        make_row(),
        CandidateDirection.LONG,
        config=config,
    )

    assert candidate.policy_version == (
        "structure_atr_v1.0"
    )


def test_structural_lookback_selects_matching_support_column() -> None:
    config = CandidateConfig(
        structural_lookback=50,
    )

    row = make_row(
        swing_low=float("nan"),
        support_20=90.0,
        support_50=96.0,
    )

    candidate = build_candidate(
        row,
        CandidateDirection.LONG,
        config=config,
    )

    # ATR stop = 97.0, so max(96.0, 97.0) = 97.0.
    assert candidate.stop_price == 97.0


def test_structural_lookback_selects_matching_resistance_column() -> None:
    config = CandidateConfig(
        structural_lookback=50,
    )

    row = make_row(
        swing_high=float("nan"),
        resistance_20=110.0,
        resistance_50=104.0,
    )

    candidate = build_candidate(
        row,
        CandidateDirection.SHORT,
        config=config,
    )

    # ATR stop = 103.0, so min(104.0, 103.0) = 103.0.
    assert candidate.stop_price == 103.0
