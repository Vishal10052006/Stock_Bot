"""Phase 11 expanded Risk Engine tests.

These tests cover the deterministic controls introduced by the Phase 11
implementation while preserving the frozen v1 research/paper policy.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trading.risk.contracts import (
    RiskAction,
    RiskPositionContext,
    RiskPositionTransition,
    RiskTransitionSizing,
    RiskReasonCode,
)
from trading.risk.engine import RiskConfig, RiskEngine, RiskInput
from trading.risk.exposure import projected_gross_exposure
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


def test_available_cash_can_resize_when_explicitly_enabled() -> None:
    """Cash constraints can reduce risk-first size without increasing risk."""
    engine = RiskEngine(RiskConfig(allow_resize=True))

    assessment = engine.evaluate(
        make_input(
            available_cash=6_200.0,
        )
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.decision.action is RiskAction.RESIZE
    assert assessment.position_size == 62.0
    assert assessment.requested_position_size == 125.0


def test_optional_drawdown_limit_has_distinct_reason_code() -> None:
    """A configured total-drawdown cap is independently auditable."""
    engine = RiskEngine(
        RiskConfig(max_drawdown_fraction=0.10)
    )

    assessment = engine.evaluate(
        make_input(
            peak_equity=100_000.0,
            available_equity=90_000.0,
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.MAX_DRAWDOWN_LIMIT



@pytest.mark.parametrize(
    ("transition", "existing", "projected"),
    [
        (RiskPositionTransition.OPEN, 0.0, 10.0),
        (RiskPositionTransition.INCREASE, 10.0, 15.0),
        (RiskPositionTransition.REDUCE, 10.0, 5.0),
        (RiskPositionTransition.FLATTEN, 10.0, 0.0),
        (RiskPositionTransition.REVERSE, 10.0, -5.0),
        (RiskPositionTransition.INCREASE, -10.0, -15.0),
        (RiskPositionTransition.REDUCE, -10.0, -5.0),
        (RiskPositionTransition.FLATTEN, -10.0, 0.0),
        (RiskPositionTransition.REVERSE, -10.0, 5.0),
    ],
)
def test_position_context_accepts_signed_transitions(
    transition: RiskPositionTransition,
    existing: float,
    projected: float,
) -> None:
    context = RiskPositionContext(
        transition=transition,
        existing_quantity=existing,
        projected_quantity=projected,
    )

    assert context.transition is transition


@pytest.mark.parametrize(
    ("transition", "existing", "projected"),
    [
        (RiskPositionTransition.OPEN, 10.0, 15.0),
        (RiskPositionTransition.INCREASE, 10.0, 5.0),
        (RiskPositionTransition.REDUCE, 10.0, -5.0),
        (RiskPositionTransition.FLATTEN, 10.0, 1.0),
        (RiskPositionTransition.REVERSE, 10.0, 5.0),
    ],
)
def test_position_context_rejects_invalid_transition_geometry(
    transition: RiskPositionTransition,
    existing: float,
    projected: float,
) -> None:
    with pytest.raises(ValueError):
        RiskPositionContext(
            transition=transition,
            existing_quantity=existing,
            projected_quantity=projected,
        )


def test_existing_position_can_reduce_without_duplicate_symbol_rejection() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REDUCE,
        existing_quantity=10.0,
        projected_quantity=5.0,
    )

    assessment = RiskEngine().evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
        )
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.decision.reason_code is RiskReasonCode.APPROVED


def test_existing_position_can_flatten_without_duplicate_symbol_rejection() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.FLATTEN,
        existing_quantity=10.0,
        projected_quantity=0.0,
    )

    assessment = RiskEngine().evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
        )
    )

    assert assessment.decision.status.value == "APPROVED"


def test_open_transition_still_rejects_duplicate_symbol() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.OPEN,
        existing_quantity=0.0,
        projected_quantity=10.0,
    )

    assessment = RiskEngine().evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
        )
    )

    assert assessment.decision.status.value == "REJECTED"
    assert assessment.decision.reason_code is RiskReasonCode.DUPLICATE_SYMBOL


def test_reduction_does_not_consume_open_position_slot() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REDUCE,
        existing_quantity=10.0,
        projected_quantity=5.0,
    )

    assessment = RiskEngine().evaluate(
        make_input(
            open_positions=3,
            symbol_already_open=True,
            position_context=context,
        )
    )

    assert assessment.decision.status.value == "APPROVED"





def test_reduction_gross_exposure_replaces_symbol_contribution() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REDUCE,
        existing_quantity=10.0,
        projected_quantity=5.0,
    )

    assert projected_gross_exposure(
        current_gross_exposure=62_000.0,
        existing_quantity=context.existing_quantity,
        projected_quantity=context.projected_quantity,
        mark_price=100.0,
    ) == 61_500.0


def test_flatten_gross_exposure_removes_symbol_contribution() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.FLATTEN,
        existing_quantity=10.0,
        projected_quantity=0.0,
    )

    assert projected_gross_exposure(
        current_gross_exposure=62_000.0,
        existing_quantity=context.existing_quantity,
        projected_quantity=context.projected_quantity,
        mark_price=100.0,
    ) == 61_000.0


def test_reverse_gross_exposure_replaces_directional_contribution() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REVERSE,
        existing_quantity=10.0,
        projected_quantity=-5.0,
    )

    assert projected_gross_exposure(
        current_gross_exposure=62_000.0,
        existing_quantity=context.existing_quantity,
        projected_quantity=context.projected_quantity,
        mark_price=100.0,
    ) == 61_500.0



@pytest.mark.parametrize(
    ("transition", "existing", "projected", "order", "closing", "opening"),
    [
        (RiskPositionTransition.OPEN, 0.0, 10.0, 10.0, 0.0, 10.0),
        (RiskPositionTransition.INCREASE, 10.0, 15.0, 5.0, 0.0, 5.0),
        (RiskPositionTransition.REDUCE, 10.0, 5.0, 5.0, 5.0, 0.0),
        (RiskPositionTransition.FLATTEN, 10.0, 0.0, 10.0, 10.0, 0.0),
        (RiskPositionTransition.REVERSE, 10.0, -5.0, 15.0, 10.0, 5.0),
        (RiskPositionTransition.INCREASE, -10.0, -15.0, 5.0, 0.0, 5.0),
        (RiskPositionTransition.REDUCE, -10.0, -5.0, 5.0, 5.0, 0.0),
        (RiskPositionTransition.FLATTEN, -10.0, 0.0, 10.0, 10.0, 0.0),
        (RiskPositionTransition.REVERSE, -10.0, 5.0, 15.0, 10.0, 5.0),
    ],
)
def test_transition_sizing_separates_close_and_open_quantities(
    transition: RiskPositionTransition,
    existing: float,
    projected: float,
    order: float,
    closing: float,
    opening: float,
) -> None:
    context = RiskPositionContext(
        transition=transition,
        existing_quantity=existing,
        projected_quantity=projected,
    )

    sizing = RiskTransitionSizing.from_context(context)

    assert sizing.order_quantity == order
    assert sizing.closing_quantity == closing
    assert sizing.opening_quantity == opening



def test_reduction_does_not_double_count_symbol_concentration() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REDUCE,
        existing_quantity=100.0,
        projected_quantity=50.0,
    )

    assessment = RiskEngine(
        RiskConfig(max_symbol_exposure_fraction=0.10)
    ).evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
            symbol_exposure={"RELIANCE": 10_000.0},
        )
    )

    assert assessment.decision.status.value == "APPROVED"


def test_reduction_does_not_double_count_sector_concentration() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.REDUCE,
        existing_quantity=100.0,
        projected_quantity=50.0,
    )

    assessment = RiskEngine(
        RiskConfig(max_sector_exposure_fraction=0.10)
    ).evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
            sector="ENERGY",
            sector_exposure={"ENERGY": 10_000.0},
            symbol_exposure={"RELIANCE": 10_000.0},
        )
    )

    assert assessment.decision.status.value == "APPROVED"


def test_flatten_does_not_require_available_cash() -> None:
    context = RiskPositionContext(
        transition=RiskPositionTransition.FLATTEN,
        existing_quantity=10.0,
        projected_quantity=0.0,
    )

    assessment = RiskEngine().evaluate(
        make_input(
            symbol_already_open=True,
            position_context=context,
            available_cash=0.0,
        )
    )

    assert assessment.decision.status.value == "APPROVED"
    assert assessment.position_size == 10.0
