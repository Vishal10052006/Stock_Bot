"""Phase 11 expanded Risk Engine tests.

These tests cover the deterministic controls introduced by the Phase 11
implementation while preserving the frozen v1 research/paper policy.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trading.risk.contracts import RiskAction, RiskReasonCode
from trading.risk.engine import RiskConfig, RiskEngine, RiskInput
from trading.risk.kill_switch import KillSwitchState
from trading.signals.models import CandidateDirection, TradeCandidate


TIMESTAMP = pd.Timestamp("2026-09-22 10:25:00+05:30")


def make_candidate(
    direction: CandidateDirection = CandidateDirection.LONG,
) -> TradeCandidate:
    """Create a fixed causal candidate with a four-point stop distance."""
    stop = 96.0 if direction is CandidateDirection.LONG else 104.0

    return TradeCandidate(
        timestamp=TIMESTAMP,
        symbol="RELIANCE",
        direction=direction,
        entry_price=100.0,
        stop_price=stop,
        policy_version="structure_atr_v1.0",
    )


def make_input(**overrides: object) -> RiskInput:
    """Create a deterministic 100,000-equity RiskInput."""
    values: dict[str, object] = {
        "timestamp": TIMESTAMP,
        "symbol": "RELIANCE",
        "candidate": make_candidate(),
        "available_equity": 100_000.0,
        "day_start_equity": 100_000.0,
    }
    values.update(overrides)
    return RiskInput(**values)


def test_reason_codes_and_action_are_machine_readable() -> None:
    """Approved decisions expose stable code/action metadata."""
    assessment = RiskEngine().evaluate(make_input())

    assert assessment.decision.reason_code is RiskReasonCode.APPROVED
    assert assessment.decision.action is RiskAction.APPROVE


def test_kill_switch_state_is_independent_of_model_output() -> None:
    """Any independent hard switch must block the candidate."""
    assessment = RiskEngine().evaluate(
        make_input(
            kill_switch_state=KillSwitchState(
                data_failure=True,
            )
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.KILL_SWITCH_ACTIVE


def test_invalid_market_data_blocks_new_trade() -> None:
    """Invalid/stale data cannot enter the execution path."""
    assessment = RiskEngine().evaluate(
        make_input(market_data_valid=False)
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.STALE_MARKET_DATA


def test_volatility_policy_can_resize_when_explicitly_enabled() -> None:
    """An explicitly configured volatility policy can reduce quantity."""
    engine = RiskEngine(
        RiskConfig(
            high_volatility_factor=0.5,
            allow_resize=True,
        )
    )

    assessment = engine.evaluate(
        make_input(
            high_volatility=True,
        )
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.decision.action is RiskAction.RESIZE
    assert assessment.decision.reason_code is RiskReasonCode.RESIZED
    assert assessment.requested_position_size == 125.0
    assert assessment.position_size == 62.0


def test_volatility_resize_is_rejected_when_policy_is_disabled() -> None:
    """The frozen v1 policy remains NO_TRADE for unapproved resizing."""
    engine = RiskEngine(
        RiskConfig(
            high_volatility_factor=0.5,
            allow_resize=False,
        )
    )

    assessment = engine.evaluate(
        make_input(
            high_volatility=True,
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.VOLATILITY_LIMIT


def test_gross_exposure_can_resize_only_when_explicitly_enabled() -> None:
    """Gross exposure remains a hard veto under frozen v1 defaults."""
    engine = RiskEngine(
        RiskConfig(
            allow_resize=True,
        )
    )

    assessment = engine.evaluate(
        make_input(
            gross_exposure=62_600.0,
        )
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.decision.action is RiskAction.RESIZE
    assert assessment.position_size == 124.0
    assert assessment.gross_exposure_after == 75_000.0


def test_symbol_concentration_is_optional_but_hard_when_configured() -> None:
    """A configured symbol cap rejects an otherwise valid trade."""
    engine = RiskEngine(
        RiskConfig(
            max_symbol_exposure_fraction=0.10,
        )
    )

    assessment = engine.evaluate(
        make_input(
            symbol_exposure={"RELIANCE": 9_500.0},
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.SYMBOL_EXPOSURE_LIMIT


def test_sector_concentration_is_optional_but_hard_when_configured() -> None:
    """A configured sector cap rejects excessive sector exposure."""
    engine = RiskEngine(
        RiskConfig(
            max_sector_exposure_fraction=0.10,
        )
    )

    assessment = engine.evaluate(
        make_input(
            sector="ENERGY",
            sector_exposure={"ENERGY": 9_500.0},
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.SECTOR_EXPOSURE_LIMIT


def test_correlation_concentration_is_optional_but_hard_when_configured() -> None:
    """A configured correlation budget can veto concentrated exposure."""
    engine = RiskEngine(
        RiskConfig(
            minimum_abs_correlation=0.80,
            max_correlated_exposure_fraction=0.50,
        )
    )

    assessment = engine.evaluate(
        make_input(
            symbol_exposure={"TCS": 50_000.0},
            pairwise_correlation={"TCS": 0.90},
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.CORRELATION_LIMIT


def test_atr_fraction_limit_can_block_extreme_volatility() -> None:
    """An explicitly frozen ATR/equity-price threshold can block a trade."""
    engine = RiskEngine(
        RiskConfig(
            max_atr_fraction=0.03,
        )
    )

    assessment = engine.evaluate(
        make_input(
            atr=4.0,
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.VOLATILITY_LIMIT


@pytest.mark.parametrize(
    ("field", "value", "reason_code"),
    [
        (
            "trades_today",
            5,
            RiskReasonCode.MAX_TRADES_REACHED,
        ),
        (
            "realized_pnl",
            -1_500.0,
            RiskReasonCode.DAILY_LOSS_LIMIT,
        ),
        (
            "open_positions",
            3,
            RiskReasonCode.MAX_OPEN_POSITIONS,
        ),
        (
            "symbol_already_open",
            True,
            RiskReasonCode.DUPLICATE_SYMBOL,
        ),
        (
            "liquidity_available",
            False,
            RiskReasonCode.LIQUIDITY_INSUFFICIENT,
        ),
    ],
)
def test_frozen_hard_limits_have_stable_reason_codes(
    field: str,
    value: object,
    reason_code: RiskReasonCode,
) -> None:
    """Every frozen hard block maps to a stable machine-readable code."""
    assessment = RiskEngine().evaluate(
        make_input(**{field: value})
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is reason_code
    assert assessment.position_size is None
