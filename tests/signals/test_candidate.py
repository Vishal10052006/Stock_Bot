from __future__ import annotations

import pandas as pd
import pytest

from trading.signals.models import (
    CandidateConfig,
    CandidateDirection,
    TradeCandidate,
)


def test_candidate_config_defaults() -> None:
    config = CandidateConfig()

    assert config.atr_period == 14
    assert config.atr_multiplier == 1.5
    assert config.structural_lookback == 20
    assert config.policy_version == "structure_atr_v1.0"
    assert config.entry_method == "DECISION_CLOSE"


def test_candidate_config_rejects_invalid_atr_period() -> None:
    with pytest.raises(
        ValueError,
        match="atr_period",
    ):
        CandidateConfig(atr_period=0)


def test_candidate_config_rejects_invalid_multiplier() -> None:
    with pytest.raises(
        ValueError,
        match="atr_multiplier",
    ):
        CandidateConfig(atr_multiplier=0)


def test_candidate_config_rejects_invalid_structural_lookback() -> None:
    with pytest.raises(
        ValueError,
        match="structural_lookback",
    ):
        CandidateConfig(structural_lookback=0)


def test_candidate_config_rejects_empty_version() -> None:
    with pytest.raises(
        ValueError,
        match="policy_version",
    ):
        CandidateConfig(policy_version="")


def test_long_candidate_is_valid() -> None:
    candidate = TradeCandidate(
        timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
        symbol="RELIANCE",
        direction=CandidateDirection.LONG,
        entry_price=100.0,
        stop_price=98.0,
        policy_version="structure_atr_v1.0",
    )

    assert candidate.direction == CandidateDirection.LONG
    assert candidate.stop_distance == 2.0


def test_short_candidate_is_valid() -> None:
    candidate = TradeCandidate(
        timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
        symbol="RELIANCE",
        direction=CandidateDirection.SHORT,
        entry_price=100.0,
        stop_price=102.0,
        policy_version="structure_atr_v1.0",
    )

    assert candidate.direction == CandidateDirection.SHORT
    assert candidate.stop_distance == 2.0


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-15 10:00:00"),
            symbol="RELIANCE",
            direction=CandidateDirection.LONG,
            entry_price=100.0,
            stop_price=98.0,
            policy_version="structure_atr_v1.0",
        )


def test_empty_symbol_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
            symbol="",
            direction=CandidateDirection.LONG,
            entry_price=100.0,
            stop_price=98.0,
            policy_version="structure_atr_v1.0",
        )


def test_non_positive_entry_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="entry_price",
    ):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
            symbol="RELIANCE",
            direction=CandidateDirection.LONG,
            entry_price=0.0,
            stop_price=98.0,
            policy_version="structure_atr_v1.0",
        )


def test_long_stop_on_wrong_side_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="LONG stop_price",
    ):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
            symbol="RELIANCE",
            direction=CandidateDirection.LONG,
            entry_price=100.0,
            stop_price=102.0,
            policy_version="structure_atr_v1.0",
        )


def test_short_stop_on_wrong_side_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="SHORT stop_price",
    ):
        TradeCandidate(
            timestamp=pd.Timestamp("2026-09-15 10:00:00+05:30"),
            symbol="RELIANCE",
            direction=CandidateDirection.SHORT,
            entry_price=100.0,
            stop_price=98.0,
            policy_version="structure_atr_v1.0",
        )
