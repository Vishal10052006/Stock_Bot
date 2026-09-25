"""Execution contract-hardening tests.

References:
- execution/integration.py
- execution/trading_execution.py
- execution/engine.py
- TRADING_SPECIFICATION.md
"""

from __future__ import annotations

import pandas as pd
import pytest

from execution.adapters.paper import PaperBrokerAdapter
from execution.engine import ExecutionEngine
from execution.integration import authorize_risk_assessment
from execution.trading_execution import ExecutionAuthorizationStatus
from trading.risk.engine import RiskAssessment
from trading.risk.gate import RiskDecision, RiskDecisionStatus
from trading.strategy.models import StrategyDirection


TS = pd.Timestamp("2026-09-25T10:00:00+05:30")


def approved_risk_decision() -> RiskDecision:
    """Create an approved risk decision for an isolated contract test."""
    return RiskDecision(
        timestamp=TS,
        symbol="ITC",
        status=RiskDecisionStatus.APPROVED,
        strategy_direction=StrategyDirection.LONG,
        reason="risk approved",
        risk_version="RISK-v1.0",
    )


def test_risk_assessment_is_preserved_in_execution_authorization():
    """Risk-selected quantity and trade economics must cross unchanged."""
    assessment = RiskAssessment(
        decision=approved_risk_decision(),
        entry_price=500.0,
        stop_price=490.0,
        target_price=515.0,
        position_size=100.0,
        risk_budget=500.0,
        stop_distance=10.0,
    )

    authorization = authorize_risk_assessment(
        approved_risk_decision(),
        assessment,
        risk_decision_id="risk-itc-001",
        max_slippage_bps=5.0,
        expires_at=TS + pd.Timedelta(minutes=5),
    )

    assert authorization.status is ExecutionAuthorizationStatus.AUTHORIZED
    assert authorization.approved_quantity == 100.0
    assert authorization.approved_notional == 50_000.0
    assert authorization.entry_price == 500.0
    assert authorization.stop_price == 490.0
    assert authorization.target_price == 515.0
    assert authorization.max_slippage_bps == 5.0
    assert authorization.expires_at == TS + pd.Timedelta(minutes=5)


def test_order_request_copies_authorized_constraints():
    """Order creation must not drop Risk-approved execution constraints."""
    assessment = RiskAssessment(
        decision=approved_risk_decision(),
        entry_price=500.0,
        stop_price=490.0,
        target_price=515.0,
        position_size=100.0,
    )

    authorization = authorize_risk_assessment(
        approved_risk_decision(),
        assessment,
        risk_decision_id="risk-itc-002",
        max_slippage_bps=7.5,
    )

    request = ExecutionEngine.from_authorization(
        authorization,
        decision_id="decision-itc-002",
    )

    assert request.entry_price == 500.0
    assert request.stop_price == 490.0
    assert request.target_price == 515.0
    assert request.max_slippage_bps == 7.5


def test_execution_rejects_constraint_tampering():
    """Execution must fail closed if an approved constraint is changed."""
    assessment = RiskAssessment(
        decision=approved_risk_decision(),
        entry_price=500.0,
        stop_price=490.0,
        target_price=515.0,
        position_size=100.0,
    )

    authorization = authorize_risk_assessment(
        approved_risk_decision(),
        assessment,
        risk_decision_id="risk-itc-003",
    )
    request = ExecutionEngine.from_authorization(
        authorization,
        decision_id="decision-itc-003",
    )

    tampered = type(request)(
        client_order_id=request.client_order_id,
        decision_id=request.decision_id,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        order_type=request.order_type,
        limit_price=request.limit_price,
        time_in_force=request.time_in_force,
        created_at=request.created_at,
        authorization=request.authorization,
        entry_price=request.entry_price,
        stop_price=request.stop_price,
        target_price=520.0,
        max_slippage_bps=request.max_slippage_bps,
        expires_at=request.expires_at,
    )

    engine = ExecutionEngine(adapter=PaperBrokerAdapter())

    with pytest.raises(ValueError, match="target_price"):
        engine.validate(tampered)


def test_expired_authorized_order_is_rejected():
    """An execution request must not be submitted after its expiry boundary."""
    assessment = RiskAssessment(
        decision=approved_risk_decision(),
        entry_price=500.0,
        stop_price=490.0,
        target_price=515.0,
        position_size=100.0,
    )

    authorization = authorize_risk_assessment(
        approved_risk_decision(),
        assessment,
        risk_decision_id="risk-itc-004",
        expires_at=TS,
    )

    request = ExecutionEngine.from_authorization(
        authorization,
        decision_id="decision-itc-004",
        created_at=TS + pd.Timedelta(seconds=1),
    )

    engine = ExecutionEngine(adapter=PaperBrokerAdapter())

    with pytest.raises(ValueError, match="expired"):
        engine.validate(request)
