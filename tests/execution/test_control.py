import pandas as pd
import pytest

from execution.control import authorize_execution
from execution.safety import IndependentSafetyGate, SafetyBlock, SafetyState, SafetyDecision
from execution.trading_execution import ExecutionAuthorizationStatus
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


def _risk(status: RiskDecisionStatus = RiskDecisionStatus.APPROVED) -> RiskDecision:
    return RiskDecision(
        timestamp=pd.Timestamp("2026-09-23T10:00:00Z"),
        symbol="ITC",
        status=status,
        strategy_direction=StrategyDirection.LONG,
        reason="test risk decision",
    )


def test_composite_control_requires_risk_approval() -> None:
    safety = SafetyDecision(True, SafetyBlock.NONE, "Safety checks passed.")

    authorization = authorize_execution(
        _risk(RiskDecisionStatus.REJECTED),
        approved_quantity=100.0,
        approved_notional=10_000.0,
        safety_decision=safety,
    )

    assert authorization.status is ExecutionAuthorizationStatus.BLOCKED
    assert authorization.approved_quantity == 0.0
    assert authorization.approved_notional == 0.0


def test_safety_veto_blocks_even_when_risk_is_approved() -> None:
    safety = IndependentSafetyGate().evaluate(
        SafetyState(kill_switch_active=True, live_execution_enabled=True)
    )

    authorization = authorize_execution(
        _risk(),
        approved_quantity=166.0,
        approved_notional=16_600.0,
        safety_decision=safety,
    )

    assert not safety.allowed
    assert safety.block is SafetyBlock.KILL_SWITCH
    assert authorization.status is ExecutionAuthorizationStatus.BLOCKED
    assert authorization.approved_quantity == 0.0
    assert authorization.approved_notional == 0.0
    assert "safety_block:KILL_SWITCH" in authorization.restrictions


def test_live_lock_is_an_execution_block() -> None:
    safety = IndependentSafetyGate().evaluate(SafetyState())

    authorization = authorize_execution(
        _risk(),
        approved_quantity=166.0,
        safety_decision=safety,
    )

    assert safety.block is SafetyBlock.LIVE_LOCKED
    assert authorization.status is ExecutionAuthorizationStatus.BLOCKED
    assert authorization.approved_quantity == 0.0


def test_both_controls_pass_and_exact_risk_quantity_is_preserved() -> None:
    safety = IndependentSafetyGate().evaluate(
        SafetyState(live_execution_enabled=True)
    )

    authorization = authorize_execution(
        _risk(),
        approved_quantity=166.0,
        approved_notional=16_600.0,
        risk_decision_id="risk-001",
        restrictions=("paper-only-test",),
        safety_decision=safety,
    )

    assert safety.allowed
    assert authorization.status is ExecutionAuthorizationStatus.AUTHORIZED
    assert authorization.approved_quantity == 166.0
    assert authorization.approved_notional == 16_600.0
    assert authorization.risk_decision_id == "risk-001"
    assert authorization.restrictions == ("paper-only-test",)


def test_safety_veto_does_not_reconstruct_or_enlarge_risk_size() -> None:
    safety = SafetyDecision(False, SafetyBlock.DATA_QUALITY, "Bad data.")

    authorization = authorize_execution(
        _risk(),
        approved_quantity=166.0,
        approved_notional=16_600.0,
        safety_decision=safety,
    )

    assert authorization.approved_quantity == 0.0
    assert authorization.approved_notional == 0.0


def test_safety_decision_type_is_required() -> None:
    with pytest.raises(TypeError, match="SafetyDecision"):
        authorize_execution(
            _risk(),
            approved_quantity=166.0,
            safety_decision=object(),  # type: ignore[arg-type]
        )