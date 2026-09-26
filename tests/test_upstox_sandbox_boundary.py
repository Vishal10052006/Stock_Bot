"""Tests for the fail-closed Upstox sandbox execution boundary."""

from datetime import datetime, timezone

import pytest

from execution.adapters.upstox import (
    UpstoxAdapterConfig,
    UpstoxBrokerAdapter,
)
from execution.broker_gateway import (
    BrokerGatewayConfig,
    BrokerIntegrationLocked,
    BrokerMode,
)
from execution.engine import OrderRequest, OrderSide


def make_order() -> OrderRequest:
    return OrderRequest(
        client_order_id="SB-SANDBOX-001",
        decision_id="decision-001",
        symbol="RELIANCE",
        side=OrderSide.BUY,
        quantity=1,
        created_at=datetime(2026, 9, 1, 9, 15, tzinfo=timezone.utc),
    )


def test_gateway_defaults_to_sandbox_and_live_submission_disabled():
    config = BrokerGatewayConfig()

    assert config.mode is BrokerMode.SANDBOX
    assert config.live_order_submission is False


def test_gateway_rejects_live_mode():
    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(mode=BrokerMode.LIVE)


def test_gateway_rejects_live_order_submission_flag():
    with pytest.raises(BrokerIntegrationLocked):
        BrokerGatewayConfig(live_order_submission=True)


def test_upstox_adapter_is_disabled_by_default():
    adapter = UpstoxBrokerAdapter(
        UpstoxAdapterConfig(
            api_base_url="https://example.test",
        )
    )

    with pytest.raises(RuntimeError, match="disabled"):
        adapter.submit(make_order())


def test_upstox_adapter_requires_external_client_when_enabled():
    adapter = UpstoxBrokerAdapter(
        UpstoxAdapterConfig(
            api_base_url="https://example.test",
            enabled=True,
        )
    )

    with pytest.raises(RuntimeError, match="No Upstox client"):
        adapter.submit(make_order())
