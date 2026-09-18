from __future__ import annotations

import pandas as pd
import pytest

from trading.signals import (
    CandidateConfig,
    CandidateDirection,
    build_directional_candidates,
)


TIMESTAMP = pd.Timestamp(
    "2026-09-15 10:00:00+05:30"
)


def make_row(**overrides) -> pd.Series:
    row = {
        "timestamp": TIMESTAMP,
        "symbol": "RELIANCE",
        "close": 100.0,
        "atr_14": 2.0,
        "swing_low": 98.0,
        "swing_high": 102.0,
        "support_20": 97.0,
        "resistance_20": 103.0,
    }

    row.update(overrides)

    return pd.Series(row)


def test_builds_long_and_short_candidates() -> None:
    long_candidate, short_candidate = (
        build_directional_candidates(make_row())
    )

    assert long_candidate.direction == CandidateDirection.LONG
    assert short_candidate.direction == CandidateDirection.SHORT

    assert long_candidate.timestamp == TIMESTAMP
    assert short_candidate.timestamp == TIMESTAMP

    assert long_candidate.symbol == "RELIANCE"
    assert short_candidate.symbol == "RELIANCE"


def test_long_stop_uses_structure_and_atr_constraint() -> None:
    long_candidate, _ = build_directional_candidates(
        make_row(
            swing_low=98.0,
        )
    )

    # entry = 100
    # ATR = 2
    # multiplier = 1.5
    # ATR stop = 97
    # structural stop = 98
    # final LONG stop = max(98, 97) = 98
    assert long_candidate.entry_price == 100.0
    assert long_candidate.stop_price == 98.0


def test_short_stop_uses_structure_and_atr_constraint() -> None:
    _, short_candidate = build_directional_candidates(
        make_row(
            swing_high=102.0,
        )
    )

    # entry = 100
    # ATR = 2
    # multiplier = 1.5
    # ATR stop = 103
    # structural stop = 102
    # final SHORT stop = min(102, 103) = 102
    assert short_candidate.entry_price == 100.0
    assert short_candidate.stop_price == 102.0


def test_falls_back_to_support_and_resistance() -> None:
    long_candidate, short_candidate = (
        build_directional_candidates(
            make_row(
                swing_low=float("nan"),
                swing_high=float("nan"),
                support_20=97.0,
                resistance_20=103.0,
            )
        )
    )

    assert long_candidate.stop_price == 97.0
    assert short_candidate.stop_price == 103.0


def test_custom_candidate_config_is_applied() -> None:
    config = CandidateConfig(
        atr_multiplier=1.0,
        structural_lookback=20,
        policy_version="structure_atr_test",
    )

    long_candidate, short_candidate = (
        build_directional_candidates(
            make_row(),
            config=config,
        )
    )

    assert long_candidate.policy_version == (
        "structure_atr_test"
    )
    assert short_candidate.policy_version == (
        "structure_atr_test"
    )

    # ATR stop = 100 - 2 = 98
    assert long_candidate.stop_price == 98.0

    # ATR stop = 100 + 2 = 102
    assert short_candidate.stop_price == 102.0


def test_timestamp_is_preserved() -> None:
    row = make_row()

    long_candidate, short_candidate = (
        build_directional_candidates(row)
    )

    assert long_candidate.timestamp == row["timestamp"]
    assert short_candidate.timestamp == row["timestamp"]


def test_symbol_is_preserved() -> None:
    row = make_row(symbol="TCS")

    long_candidate, short_candidate = (
        build_directional_candidates(row)
    )

    assert long_candidate.symbol == "TCS"
    assert short_candidate.symbol == "TCS"


def test_missing_long_structural_reference_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="LONG structural stop",
    ):
        build_directional_candidates(
            make_row(
                swing_low=float("nan"),
                support_20=float("nan"),
            )
        )


def test_missing_short_structural_reference_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="SHORT structural stop",
    ):
        build_directional_candidates(
            make_row(
                swing_high=float("nan"),
                resistance_20=float("nan"),
            )
        )


def test_no_future_columns_are_required() -> None:
    row = make_row(
        future_close=999.0,
        outcome_price=999.0,
        future_return=99.0,
    )

    long_candidate, short_candidate = (
        build_directional_candidates(row)
    )

    assert long_candidate.entry_price == 100.0
    assert short_candidate.entry_price == 100.0
    assert long_candidate.stop_price == 98.0
    assert short_candidate.stop_price == 102.0
