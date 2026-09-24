"""Execution Engine validation suite.

These tests cover the broker-neutral execution contract, authorization
boundary, state transitions, idempotency, partial fills, cancellation,
reconciliation, and fail-closed live readiness.
"""

from __future__ import annotations

import pandas as pd
import pytest

from execution.engine import (
    ExecutionEngine,
    OrderRequest,
    OrderSide,
    OrderStateMachine,
    OrderStatus,
    OrderType,
)
from execution.adapters.paper import PaperAdapterConfig, PaperBrokerAdapter
from execution.trading_execution import (
    ExecutionAuthorization,
    ExecutionAuthorizationStatus,
)
from trading.strategy.models import StrategyDirection


TS = pd.Timestamp("2026-09-24T10:00:00+05:30")


def authorization(
    direction: StrategyDirection = StrategyDirection.LONG,
    quantity: float = 100.0,
) -> ExecutionAuthorization:
    """Create an explicitly risk-approved authorization for isolated tests."""
    return ExecutionAuthorization(
        timestamp=TS,
        symbol="ITC",
        direction=direction,
        status=ExecutionAuthorizationStatus.AUTHORIZED,
        reason="test approval",
        risk_version="RISK-v1.0",
        approved_quantity=quantity,
        approved_notional=quantity * 100.0,
        risk_decision_id="risk-test-001",
    )


def order_request() -> OrderRequest:
    """Create one deterministic market order request."""
    auth = authorization()
    return ExecutionEngine.from_authorization(
        auth,
        decision_id="decision-test-001",
    )


def test_order_request_is_risk_sized_exactly():
    request = order_request()

    assert request.quantity == 100.0
    assert request.side is OrderSide.BUY
    assert request.order_type is OrderType.MARKET
    assert request.authorization is not None


def test_unapproved_authorization_cannot_create_order():
    auth = ExecutionAuthorization(
        timestamp=TS,
        symbol="ITC",
        direction=StrategyDirection.LONG,
        status=ExecutionAuthorizationStatus.BLOCKED,
        reason="blocked",
        risk_version="RISK-v1.0",
    )

    with pytest.raises(ValueError, match="requires AUTHORIZED"):
        ExecutionEngine.from_authorization(
            auth,
            decision_id="blocked-decision",
        )


def test_execution_requires_exact_risk_quantity():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    auth = authorization(quantity=100.0)
    request = ExecutionEngine.from_authorization(
        auth,
        decision_id="decision-exact-size",
    )

    with pytest.raises(ValueError, match="exactly equal"):
        bad_request = OrderRequest(
            client_order_id=request.client_order_id,
            decision_id=request.decision_id,
            symbol=request.symbol,
            side=request.side,
            quantity=101.0,
            authorization=auth,
        )
        engine.validate(bad_request)


def test_order_submission_is_idempotent():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()

    first = engine.submit(request)
    second = engine.submit(request)

    assert first.snapshot.broker_order_id == second.snapshot.broker_order_id
    assert len(engine.journal) == 1


def test_paper_order_is_filled_and_journaled():
    adapter = PaperBrokerAdapter(
        price_provider=lambda _order: 200.0,
    )
    engine = ExecutionEngine(adapter)
    result = engine.submit(order_request())

    assert result.accepted
    assert result.filled
    assert result.snapshot.filled_quantity == 100.0
    assert result.snapshot.average_fill_price is not None
    assert len(engine.fills(order_request().client_order_id)) == 1


def test_partial_fill_is_preserved():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.4,
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )
    engine = ExecutionEngine(adapter)
    result = engine.submit(order_request())

    assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert result.snapshot.filled_quantity == 40.0


def test_refresh_marks_missing_broker_state_unknown():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)
    adapter._orders.pop(request.client_order_id)

    refreshed = engine.refresh(request.client_order_id)

    assert refreshed.status is OrderStatus.UNKNOWN


def test_cancel_persists_broker_state():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(partial_fill_ratio=0.5)
    )
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    cancelled = engine.cancel(request.client_order_id)

    assert cancelled.status is OrderStatus.CANCELLED


def test_position_reconciliation_detects_match_and_mismatch():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    broker_positions = adapter.positions()

    assert engine.reconcile_positions(broker_positions)

    altered = tuple(
        type(position)(
            symbol=position.symbol,
            quantity=position.quantity + 1.0,
            average_price=position.average_price,
        )
        for position in broker_positions
    )

    assert not engine.reconcile_positions(altered)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.CREATED, OrderStatus.VALIDATED),
        (OrderStatus.VALIDATED, OrderStatus.SUBMITTING),
        (OrderStatus.SUBMITTING, OrderStatus.SUBMITTED),
        (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
        (OrderStatus.OPEN, OrderStatus.CANCEL_PENDING),
        (OrderStatus.CANCEL_PENDING, OrderStatus.CANCELLED),
    ],
)
def test_valid_order_state_transitions(current: OrderStatus, target: OrderStatus):
    assert OrderStateMachine.transition(current, target) is target


def test_invalid_order_state_transition_rejected():
    with pytest.raises(ValueError, match="invalid order transition"):
        OrderStateMachine.transition(
            OrderStatus.FILLED,
            OrderStatus.SUBMITTED,
        )


def test_short_authorization_maps_to_sell():
    auth = authorization(
        direction=StrategyDirection.SHORT,
        quantity=25.0,
    )
    request = ExecutionEngine.from_authorization(
        auth,
        decision_id="short-decision",
    )

    assert request.side is OrderSide.SELL
    assert request.quantity == 25.0



def test_short_paper_execution_creates_signed_short_position():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 150.0,
    )
    engine = ExecutionEngine(adapter)
    auth = authorization(
        direction=StrategyDirection.SHORT,
        quantity=20.0,
    )
    request = ExecutionEngine.from_authorization(
        auth,
        decision_id="short-paper",
    )

    result = engine.submit(request)

    assert result.filled
    positions = adapter.positions()
    assert len(positions) == 1
    assert positions[0].symbol == "ITC"
    assert positions[0].quantity == -20.0
    assert positions[0].average_price == 150.0


def test_lifecycle_events_are_recorded_in_order():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)

    result = engine.submit(order_request())

    events = engine.events

    assert [event.to_status for event in events] == [
        OrderStatus.VALIDATED,
        OrderStatus.SUBMITTING,
        OrderStatus.FILLED,
    ]
    assert result.snapshot.status is OrderStatus.FILLED


def test_execution_metrics_include_fills_and_fees():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            slippage_bps=0.0,
            fee_bps=2.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)

    engine.submit(order_request())
    metrics = engine.metrics()

    assert metrics.orders == 1
    assert metrics.filled_orders == 1
    assert metrics.requested_quantity == 100.0
    assert metrics.filled_quantity == 100.0
    assert metrics.fill_ratio == 1.0
    assert metrics.total_fees > 0.0
