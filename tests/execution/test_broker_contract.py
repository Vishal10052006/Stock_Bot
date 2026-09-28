"""Contract tests for the broker-neutral execution boundary.

These tests exercise the same BrokerAdapter shape used by paper execution and
verify that the locked broker gateway cannot accidentally acquire live authority.
"""

import pandas as pd
import pytest

from execution.adapters.paper import PaperBrokerAdapter
from execution.broker_gateway import (
    BrokerIntegrationLocked,
    LockedBrokerGateway,
)
from execution.engine import (
    BrokerAdapter,
    OrderRequest,
    OrderSide,
    OrderType,
    TimeInForce,
)


def make_order() -> OrderRequest:
    return OrderRequest(
        client_order_id="CONTRACT-001",
        decision_id="decision-contract",
        symbol="ITC",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        time_in_force=TimeInForce.DAY,
        created_at=pd.Timestamp("2026-09-26T09:15:00+05:30"),
    )


def test_paper_adapter_matches_broker_contract():
    adapter = PaperBrokerAdapter(price_provider=lambda _: 100.0)

    assert isinstance(adapter, BrokerAdapter)
    snapshot = adapter.submit(make_order())

    assert snapshot.client_order_id == "CONTRACT-001"
    assert snapshot.requested_quantity == 10
    assert adapter.get_order("CONTRACT-001") == snapshot
    assert adapter.positions()


def test_paper_adapter_submission_is_idempotent():
    adapter = PaperBrokerAdapter(price_provider=lambda _: 100.0)
    order = make_order()

    first = adapter.submit(order)
    second = adapter.submit(order)

    assert second == first
    assert len(adapter.positions()) == 1


def test_locked_gateway_blocks_every_broker_operation():
    gateway = LockedBrokerGateway(PaperBrokerAdapter())
    order = make_order()

    with pytest.raises(BrokerIntegrationLocked):
        gateway.submit(order)
    with pytest.raises(BrokerIntegrationLocked):
        gateway.get_order(order.client_order_id)
    with pytest.raises(BrokerIntegrationLocked):
        gateway.cancel(order.client_order_id)
    with pytest.raises(BrokerIntegrationLocked):
        gateway.positions()


def test_locked_gateway_evidence_is_non_authoritative():
    gateway = LockedBrokerGateway(PaperBrokerAdapter())
    evidence = gateway.evidence()

    assert evidence["status"] == "LOCKED"
    assert evidence["live_broker_order_submission"] is False
    assert evidence["broker_network_authority"] is False


def test_live_gateway_configuration_is_rejected():
    from execution.broker_gateway import BrokerGatewayConfig, BrokerMode

    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(mode=BrokerMode.LIVE)

    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(live_order_submission=True)
