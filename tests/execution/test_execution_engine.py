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


def _snapshot_for(
    order: OrderRequest,
    *,
    status: OrderStatus,
    requested: float,
    filled: float,
    fill_quantity: float | None = None,
) -> object:
    from execution.engine import Fill, OrderSnapshot

    fills = ()
    if fill_quantity is not None:
        fills = (
            Fill(
                fill_id="F-1",
                client_order_id=order.client_order_id,
                quantity=fill_quantity,
                price=100.0,
            ),
        )
    return OrderSnapshot(
        broker_order_id="BROKER-1",
        client_order_id=order.client_order_id,
        status=status,
        requested_quantity=requested,
        filled_quantity=filled,
        average_fill_price=100.0 if filled else None,
        fills=fills,
    )


class _StaticAdapter:
    def __init__(self, snapshot_factory):
        self.snapshot_factory = snapshot_factory

    def submit(self, order):
        return self.snapshot_factory(order)

    def get_order(self, client_order_id):
        return None

    def cancel(self, client_order_id):
        raise NotImplementedError

    def positions(self):
        return ()


def test_broker_response_rejects_filled_quantity_over_request():
    adapter = _StaticAdapter(
        lambda order: _snapshot_for(
            order,
            status=OrderStatus.PARTIALLY_FILLED,
            requested=order.quantity,
            filled=order.quantity + 1.0,
            fill_quantity=order.quantity,
        )
    )
    engine = ExecutionEngine(adapter)

    with pytest.raises(ValueError, match="exceeds requested"):
        engine.submit(order_request())


def test_broker_response_rejects_mismatched_fill_identity():
    from execution.engine import Fill, OrderSnapshot

    def bad_snapshot(order):
        return OrderSnapshot(
            broker_order_id="BROKER-2",
            client_order_id=order.client_order_id,
            status=OrderStatus.FILLED,
            requested_quantity=order.quantity,
            filled_quantity=order.quantity,
            average_fill_price=100.0,
            fills=(
                Fill(
                    fill_id="F-2",
                    client_order_id="OTHER-ORDER",
                    quantity=order.quantity,
                    price=100.0,
                ),
            ),
        )

    engine = ExecutionEngine(_StaticAdapter(bad_snapshot))

    with pytest.raises(ValueError, match="fill client_order_id"):
        engine.submit(order_request())


def test_filled_status_requires_full_requested_quantity():
    adapter = _StaticAdapter(
        lambda order: _snapshot_for(
            order,
            status=OrderStatus.FILLED,
            requested=order.quantity,
            filled=order.quantity - 1.0,
            fill_quantity=order.quantity - 1.0,
        )
    )
    engine = ExecutionEngine(adapter)

    with pytest.raises(ValueError, match="FILLED"):
        engine.submit(order_request())


def test_position_reconciliation_rejects_duplicate_local_symbols():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)

    duplicate = (
        type("P", (), {"symbol": "ITC", "quantity": 10.0, "average_price": 100.0})(),
        type("P", (), {"symbol": "ITC", "quantity": 20.0, "average_price": 100.0})(),
    )

    assert not engine.reconcile_positions(duplicate)


def test_position_reconciliation_accepts_empty_broker_and_local_state():
    engine = ExecutionEngine(PaperBrokerAdapter())
    assert engine.reconcile_positions(())


def test_partial_fill_position_is_authoritative_and_reconcilable():
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.4,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = order_request()

    result = engine.submit(request)

    assert result.snapshot.status is OrderStatus.PARTIALLY_FILLED
    broker_positions = adapter.positions()
    assert broker_positions[0].quantity == 40.0
    assert engine.reconcile_positions(broker_positions)


def test_partial_fill_can_complete_remaining_quantity_and_reconcile() -> None:
    """A 6/10 partial fill can later complete the remaining 4 shares."""
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = order_request()

    first = engine.submit(request)
    assert first.snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert first.snapshot.filled_quantity == 60.0
    assert adapter.positions()[0].quantity == 60.0

    completed = adapter.fill_remaining(request.client_order_id)
    refreshed = engine.refresh(request.client_order_id)

    assert completed.status is OrderStatus.FILLED
    assert completed.requested_quantity == 100.0
    assert completed.filled_quantity == 100.0
    assert len(completed.fills) == 2
    assert refreshed.status is OrderStatus.FILLED
    assert refreshed.filled_quantity == 100.0
    assert adapter.positions()[0].quantity == 100.0
    assert engine.reconcile_positions(adapter.positions())


def test_partial_short_fill_can_complete_remaining_quantity() -> None:
    """Short positions remain signed while a partial order completes."""
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.4,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = ExecutionEngine.from_authorization(
        authorization(
            direction=StrategyDirection.SHORT,
            quantity=10.0,
        ),
        decision_id="partial-short-complete",
    )

    first = engine.submit(request)
    assert first.snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert first.snapshot.filled_quantity == 4.0
    assert adapter.positions()[0].quantity == -4.0

    completed = adapter.fill_remaining(request.client_order_id)
    refreshed = engine.refresh(request.client_order_id)

    assert completed.status is OrderStatus.FILLED
    assert completed.filled_quantity == 10.0
    assert refreshed.status is OrderStatus.FILLED
    assert refreshed.filled_quantity == 10.0
    assert adapter.positions()[0].quantity == -10.0
    assert engine.reconcile_positions(adapter.positions())


def test_partial_fill_cancellation_preserves_only_actual_filled_position() -> None:
    """Cancelling the remainder must never manufacture additional exposure."""
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = order_request()

    first = engine.submit(request)
    assert first.snapshot.status is OrderStatus.PARTIALLY_FILLED
    assert first.snapshot.filled_quantity == 60.0
    assert adapter.positions()[0].quantity == 60.0

    cancelled = engine.cancel(request.client_order_id)
    refreshed = engine.refresh(request.client_order_id)

    assert cancelled.status is OrderStatus.CANCELLED
    assert cancelled.filled_quantity == 60.0
    assert refreshed.status is OrderStatus.CANCELLED
    assert refreshed.filled_quantity == 60.0
    assert adapter.positions()[0].quantity == 60.0
    assert len(engine.fills(request.client_order_id)) == 1

    with pytest.raises(ValueError, match="partially filled"):
        adapter.fill_remaining(request.client_order_id)

    assert adapter.positions()[0].quantity == 60.0
    assert engine.reconcile_positions(adapter.positions())


def test_partial_short_cancellation_preserves_signed_filled_quantity() -> None:
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.4,
            slippage_bps=0.0,
            fee_bps=0.0,
        )
    )
    engine = ExecutionEngine(adapter)
    request = ExecutionEngine.from_authorization(
        authorization(
            direction=StrategyDirection.SHORT,
            quantity=10.0,
        ),
        decision_id="partial-short-cancel",
    )

    first = engine.submit(request)
    assert first.snapshot.filled_quantity == 4.0
    assert adapter.positions()[0].quantity == -4.0

    cancelled = engine.cancel(request.client_order_id)

    assert cancelled.status is OrderStatus.CANCELLED
    assert cancelled.filled_quantity == 4.0
    assert adapter.positions()[0].quantity == -4.0
    assert engine.reconcile_positions(adapter.positions())


def test_cancel_fill_race_accepts_authoritative_filled_state() -> None:
    """A fill that wins a cancellation race must become authoritative."""
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(
            partial_fill_ratio=0.6,
            slippage_bps=0.0,
            fee_bps=0.0,
        ),
        price_provider=lambda _order: 100.0,
    )
    engine = ExecutionEngine(adapter)
    request = order_request()

    first = engine.submit(request)
    assert first.snapshot.filled_quantity == 60.0

    cancelled = engine.cancel(request.client_order_id)
    assert cancelled.status is OrderStatus.CANCELLED
    assert adapter.positions()[0].quantity == 60.0

    adapter.fill_remaining(request.client_order_id, after_cancel=True)
    refreshed = engine.refresh(request.client_order_id)

    assert refreshed.status is OrderStatus.FILLED
    assert refreshed.filled_quantity == 100.0
    assert len(refreshed.fills) == 2
    assert adapter.positions()[0].quantity == 100.0
    assert engine.reconcile_positions(adapter.positions())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quantity", float("inf")),
        ("quantity", float("nan")),
    ],
)
def test_position_snapshot_rejects_non_finite_quantity(field: str, value: float) -> None:
    from execution.engine import PositionSnapshot

    kwargs = {"symbol": "ITC", "quantity": 1.0, "average_price": 100.0}
    kwargs[field] = value
    with pytest.raises(ValueError, match="finite"):
        PositionSnapshot(**kwargs)


def test_position_snapshot_rejects_non_finite_average_price() -> None:
    from execution.engine import PositionSnapshot

    with pytest.raises(ValueError, match="finite"):
        PositionSnapshot(symbol="ITC", quantity=1.0, average_price=float("inf"))


def test_refresh_rejects_inconsistent_fill_total() -> None:
    """A broker snapshot cannot claim 10 filled while exposing only 6 fills."""
    from execution.engine import Fill, OrderSnapshot

    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    bad = OrderSnapshot(
        broker_order_id="PAPER-1",
        client_order_id=request.client_order_id,
        status=OrderStatus.PARTIALLY_FILLED,
        requested_quantity=request.quantity,
        filled_quantity=60.0,
        average_fill_price=100.0,
        fills=(
            Fill(
                fill_id="ONLY-6",
                client_order_id=request.client_order_id,
                quantity=6.0,
                price=100.0,
            ),
        ),
    )

    adapter._orders[request.client_order_id] = bad
    with pytest.raises(ValueError, match="fill total"):
        engine.refresh(request.client_order_id)


def test_refresh_rejects_duplicate_fill_ids() -> None:
    from execution.engine import Fill, OrderSnapshot

    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    fill = Fill(
        fill_id="DUP",
        client_order_id=request.client_order_id,
        quantity=50.0,
        price=100.0,
    )
    bad = OrderSnapshot(
        broker_order_id="PAPER-1",
        client_order_id=request.client_order_id,
        status=OrderStatus.PARTIALLY_FILLED,
        requested_quantity=request.quantity,
        filled_quantity=100.0,
        average_fill_price=100.0,
        fills=(fill, fill),
    )
    adapter._orders[request.client_order_id] = bad

    with pytest.raises(ValueError, match="duplicate fill"):
        engine.refresh(request.client_order_id)


def test_cancel_validates_authoritative_broker_snapshot() -> None:
    adapter = PaperBrokerAdapter(
        config=PaperAdapterConfig(partial_fill_ratio=0.5)
    )
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    original_cancel = adapter.cancel

    def malformed_cancel(client_order_id: str):
        snapshot = original_cancel(client_order_id)
        return type(snapshot)(
            broker_order_id=snapshot.broker_order_id,
            client_order_id=snapshot.client_order_id,
            status=snapshot.status,
            requested_quantity=snapshot.requested_quantity,
            filled_quantity=100.0,
            average_fill_price=snapshot.average_fill_price,
            reason=snapshot.reason,
            fills=snapshot.fills,
        )

    adapter.cancel = malformed_cancel  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="fill total|CANCELLED"):
        engine.cancel(request.client_order_id)


def test_position_reconciliation_rejects_missing_broker_symbol():
    from execution.engine import PositionSnapshot

    engine = ExecutionEngine(PaperBrokerAdapter())
    local = (
        PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
        PositionSnapshot(symbol="TCS", quantity=5.0, average_price=200.0),
    )
    broker = (
        PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
    )

    adapter = engine.adapter
    adapter._positions = {
        "ITC": broker[0],
    }

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_rejects_missing_local_symbol():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    adapter._positions = {
        "ITC": PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
        "TCS": PositionSnapshot(symbol="TCS", quantity=5.0, average_price=200.0),
    }
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
    )

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_rejects_long_short_sign_mismatch():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    adapter._positions = {
        "ITC": PositionSnapshot(symbol="ITC", quantity=-10.0, average_price=100.0),
    }
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
    )

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_normalizes_symbol_case_and_whitespace():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    adapter._positions = {
        "ITC": PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
    }
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(symbol=" itc ", quantity=10.0, average_price=100.0),
    )

    assert engine.reconcile_positions(local)


@pytest.mark.parametrize("bad_quantity", [float("nan"), float("inf"), float("-inf")])
def test_position_reconciliation_rejects_non_finite_duck_typed_quantity(bad_quantity):
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)

    local = (
        type("P", (), {
            "symbol": "ITC",
            "quantity": bad_quantity,
            "average_price": 100.0,
        })(),
    )

    assert not engine.reconcile_positions(local)


@pytest.mark.parametrize("bad_price", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_position_reconciliation_rejects_invalid_duck_typed_average_price(bad_price):
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)

    local = (
        type("P", (), {
            "symbol": "ITC",
            "quantity": 10.0,
            "average_price": bad_price,
        })(),
    )

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_rejects_zero_quantity_position():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(symbol="ITC", quantity=0.0, average_price=100.0),
    )

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_accepts_tiny_float_rounding_difference():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    adapter._positions = {
        "ITC": PositionSnapshot(
            symbol="ITC",
            quantity=10.0,
            average_price=100.0,
        ),
    }
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(
            symbol="ITC",
            quantity=10.0 + 5e-13,
            average_price=100.0 + 5e-13,
        ),
    )

    assert engine.reconcile_positions(local)


def test_position_reconciliation_rejects_material_quantity_difference():
    from execution.engine import PositionSnapshot

    adapter = PaperBrokerAdapter()
    adapter._positions = {
        "ITC": PositionSnapshot(symbol="ITC", quantity=10.0, average_price=100.0),
    }
    engine = ExecutionEngine(adapter)

    local = (
        PositionSnapshot(symbol="ITC", quantity=10.0001, average_price=100.0),
    )

    assert not engine.reconcile_positions(local)


def test_position_reconciliation_rejects_duplicate_broker_symbols():
    class DuplicateBroker(PaperBrokerAdapter):
        def positions(self):
            return (
                type("P", (), {"symbol": "ITC", "quantity": 10.0, "average_price": 100.0})(),
                type("P", (), {"symbol": "itc", "quantity": 10.0, "average_price": 100.0})(),
            )

    engine = ExecutionEngine(DuplicateBroker())
    local = (
        type("P", (), {"symbol": "ITC", "quantity": 10.0, "average_price": 100.0})(),
    )

    assert not engine.reconcile_positions(local)


def test_order_reconciliation_requires_validated_authoritative_snapshot():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    good = adapter.get_order(request.client_order_id)
    assert good is not None
    assert engine.reconcile_order(request.client_order_id)

    from execution.engine import OrderSnapshot
    adapter._orders[request.client_order_id] = OrderSnapshot(
        broker_order_id=good.broker_order_id,
        client_order_id=request.client_order_id,
        status=good.status,
        requested_quantity=good.requested_quantity,
        filled_quantity=good.filled_quantity,
        average_fill_price=good.average_fill_price,
        fills=(),
    )

    assert not engine.reconcile_order(request.client_order_id)


def test_order_reconciliation_detects_average_price_rounding_but_allows_tiny_noise():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    from execution.engine import OrderSnapshot
    good = adapter.get_order(request.client_order_id)
    assert good is not None

    adapter._orders[request.client_order_id] = OrderSnapshot(
        broker_order_id=good.broker_order_id,
        client_order_id=good.client_order_id,
        status=good.status,
        requested_quantity=good.requested_quantity,
        filled_quantity=good.filled_quantity,
        average_fill_price=good.average_fill_price + 5e-13,
        fills=good.fills,
    )
    assert engine.reconcile_order(request.client_order_id)

    adapter._orders[request.client_order_id] = OrderSnapshot(
        broker_order_id=good.broker_order_id,
        client_order_id=good.client_order_id,
        status=good.status,
        requested_quantity=good.requested_quantity,
        filled_quantity=good.filled_quantity,
        average_fill_price=good.average_fill_price + 1e-4,
        fills=good.fills,
    )
    assert not engine.reconcile_order(request.client_order_id)


def test_order_reconciliation_rejects_missing_local_request():
    adapter = PaperBrokerAdapter()
    engine = ExecutionEngine(adapter)
    request = order_request()
    engine.submit(request)

    engine._order_requests.pop(request.client_order_id)

    assert not engine.reconcile_order(request.client_order_id)
