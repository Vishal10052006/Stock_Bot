from __future__ import annotations

import os

import pytest

from execution.adapters.upstox_sandbox import (
    SANDBOX_BASE_URL,
    UpstoxSandboxClient,
)


def test_sandbox_client_rejects_non_sandbox_base_url():
    with pytest.raises(ValueError, match="only permits"):
        UpstoxSandboxClient(
            access_token="sandbox-token",
            base_url="https://api-hft.upstox.com",
        )


def test_sandbox_client_requires_token():
    with pytest.raises(ValueError, match="access_token"):
        UpstoxSandboxClient(access_token="")


def test_sandbox_client_defaults_to_dedicated_sandbox_host():
    client = UpstoxSandboxClient(access_token="sandbox-token")
    assert client.base_url == SANDBOX_BASE_URL


@pytest.mark.integration
def test_real_upstox_sandbox_order_lifecycle():
    """Opt-in provider validation; never runs in normal CI.

    Required environment:
      UPSTOX_SANDBOX_ACCESS_TOKEN
      UPSTOX_SANDBOX_INSTRUMENT_TOKEN
      UPSTOX_SANDBOX_PRICE

    UPSTOX_SANDBOX_CONFIRM=YES is additionally required before any order
    placement is attempted.
    """
    token = os.getenv("UPSTOX_SANDBOX_ACCESS_TOKEN")
    instrument = os.getenv("UPSTOX_SANDBOX_INSTRUMENT_TOKEN")
    price = os.getenv("UPSTOX_SANDBOX_PRICE")

    if not token or not instrument or not price:
        pytest.skip(
            "Set UPSTOX_SANDBOX_ACCESS_TOKEN, "
            "UPSTOX_SANDBOX_INSTRUMENT_TOKEN and UPSTOX_SANDBOX_PRICE "
            "for real sandbox validation."
        )

    if os.getenv("UPSTOX_SANDBOX_CONFIRM") != "YES":
        pytest.skip("Set UPSTOX_SANDBOX_CONFIRM=YES to opt into order placement.")

    from execution.adapters.upstox import UpstoxAdapterConfig, UpstoxBrokerAdapter
    from execution.adapters.upstox_sandbox import UpstoxSandboxClient
    from execution.engine import OrderRequest, OrderSide, OrderStatus, OrderType

    client = UpstoxSandboxClient(token)

    adapter = UpstoxBrokerAdapter(
        UpstoxAdapterConfig(
            api_base_url=SANDBOX_BASE_URL,
            enabled=True,
            instrument_token_resolver=lambda symbol: instrument,
        ),
        client=client,
    )

    request = OrderRequest(
        client_order_id=f"SB-SBX-{os.urandom(8).hex()}",
        decision_id="sandbox-validation",
        symbol="SANDBOX",
        side=OrderSide.BUY,
        quantity=1,
        order_type=OrderType.LIMIT,
        limit_price=float(price),
    )

    placed = adapter.submit(request)
    assert placed.broker_order_id
    assert placed.client_order_id == request.client_order_id

    looked_up = adapter.get_order(request.client_order_id)
    assert looked_up is not None
    assert looked_up.broker_order_id == placed.broker_order_id
    assert looked_up.requested_quantity == placed.requested_quantity

    if looked_up.status in {
        OrderStatus.OPEN,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.SUBMITTED,
    }:
        cancelled = adapter.cancel(request.client_order_id)
        assert cancelled.broker_order_id == placed.broker_order_id
        assert cancelled.status in {
            OrderStatus.CANCELLED,
            OrderStatus.CANCEL_PENDING,
        }
    else:
        pytest.skip(
            f"Sandbox order reached terminal state {looked_up.status.value}; "
            "cancellation was not observable for this run."
        )

    positions = adapter.positions()
    assert isinstance(positions, tuple)
