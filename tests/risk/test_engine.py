"""Focused tests for the deterministic Risk Engine."""

from __future__ import annotations

import pandas as pd
import pytest

from trading.risk.engine import RiskEngine, RiskInput
from trading.signals.models import (
    CandidateDirection,
    TradeCandidate,
)


TIMESTAMP = pd.Timestamp(
    "2026-09-22 10:25:00+05:30"
)


def make_candidate(
    direction: CandidateDirection = CandidateDirection.LONG,
) -> TradeCandidate:
    """Create a fixed causal candidate with a four-point stop distance."""
    if direction is CandidateDirection.LONG:
        stop = 96.0
    else:
        stop = 104.0

    return TradeCandidate(
        timestamp=TIMESTAMP,
        symbol="RELIANCE",
        direction=direction,
        entry_price=100.0,
        stop_price=stop,
        policy_version="structure_atr_v1.0",
    )


def make_input(**overrides: object) -> RiskInput:
    """Create a deterministic risk input for a 100,000-equity account."""
    values: dict[str, object] = {
        "timestamp": TIMESTAMP,
        "symbol": "RELIANCE",
        "candidate": make_candidate(),
        "available_equity": 100_000.0,
        "day_start_equity": 100_000.0,
    }
    values.update(overrides)
    return RiskInput(**values)


def test_risk_engine_sizes_from_risk_budget() -> None:
    """0.5% of 100,000 is 500; 500 / 4 = 125 shares."""
    assessment = RiskEngine().evaluate(
        make_input()
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.position_size == 125.0
    assert assessment.risk_budget == 500.0
    assert assessment.stop_distance == 4.0
    assert assessment.target_price == 106.0
    assert assessment.gross_exposure_after == 12_500.0


def test_short_target_is_below_entry() -> None:
    assessment = RiskEngine().evaluate(
        make_input(
            candidate=make_candidate(
                CandidateDirection.SHORT
            )
        )
    )

    assert assessment.decision.strategy_direction.value == "SHORT"
    assert assessment.target_price == 94.0


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        (
            "kill_switch_active",
            True,
            "Kill switch is active.",
        ),
        (
            "liquidity_available",
            False,
            "Liquidity is insufficient.",
        ),
        (
            "trades_today",
            5,
            "Maximum daily trade entries reached.",
        ),
        (
            "realized_pnl",
            -1500.0,
            "Daily loss limit reached.",
        ),
        (
            "open_positions",
            3,
            "Maximum open positions reached.",
        ),
        (
            "symbol_already_open",
            True,
            "Symbol already has an open position.",
        ),
    ],
)
def test_hard_risk_blocks(
    field: str,
    value: object,
    expected: str,
) -> None:
    assessment = RiskEngine().evaluate(
        make_input(**{field: value})
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason == expected
    assert assessment.position_size is None


def test_gross_exposure_limit_rejects_before_approval() -> None:
    assessment = RiskEngine().evaluate(
        make_input(
            gross_exposure=62_600.0
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert "gross exposure" in assessment.decision.reason.lower()


def test_risk_input_requires_causal_identity() -> None:
    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        RiskInput(
            timestamp=TIMESTAMP + pd.Timedelta(minutes=5),
            symbol="RELIANCE",
            candidate=make_candidate(),
            available_equity=100_000.0,
            day_start_equity=100_000.0,
        )
