from __future__ import annotations

import json
import os

import pytest

import execution.adapters.upstox_sandbox as sandbox
from execution.adapters.upstox_sandbox import (
    SANDBOX_BASE_URL,
    UpstoxSandboxClient,
)
from execution.adapters.upstox_sdk import UpstoxSDKSandboxClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


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


def test_place_order_uses_sandbox_endpoint_and_enriches_response(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.method
        seen["authorization"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"status": "success", "data": {"order_id": "SB-1"}})

    monkeypatch.setattr(sandbox, "urlopen", fake_urlopen)
    client = UpstoxSandboxClient("sandbox-secret")

    result = client.place_order({"tag": "SB-TAG", "quantity": 1})

    assert seen["url"] == f"{SANDBOX_BASE_URL}/v2/order/place"
    assert seen["method"] == "POST"
    assert seen["authorization"] == "Bearer sandbox-secret"
    assert seen["body"] == {"tag": "SB-TAG", "quantity": 1}
    assert result["data"]["order_id"] == "SB-1"
    assert result["data"]["tag"] == "SB-TAG"
    assert result["data"]["quantity"] == 1
    assert result["data"]["status"] == "put order req received"


def test_find_order_by_tag_normalizes_latest_history_record(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        return FakeResponse(
            {
                "status": "success",
                "data": [
                    {"order_id": "SB-1", "status": "open", "tag": None},
                    {"order_id": "SB-1", "status": "cancelled", "tag": None},
                ],
            }
        )

    monkeypatch.setattr(sandbox, "urlopen", fake_urlopen)
    result = UpstoxSandboxClient("sandbox-secret").find_order_by_tag("SB-TAG")

    assert seen["url"] == f"{SANDBOX_BASE_URL}/v2/order/history?tag=SB-TAG"
    assert result["data"]["order_id"] == "SB-1"
    assert result["data"]["status"] == "cancelled"
    assert result["data"]["tag"] == "SB-TAG"


def test_cancel_order_cancels_then_reads_authoritative_history(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.method, request.full_url))
        if request.method == "DELETE":
            return FakeResponse({"status": "success", "data": {"order_id": "SB-1"}})
        return FakeResponse(
            {
                "status": "success",
                "data": [{"order_id": "SB-1", "status": "cancelled"}],
            }
        )

    monkeypatch.setattr(sandbox, "urlopen", fake_urlopen)
    result = UpstoxSandboxClient("sandbox-secret").cancel_order("SB-1")

    assert calls == [
        ("DELETE", f"{SANDBOX_BASE_URL}/v2/order/cancel?order_id=SB-1"),
        ("GET", f"{SANDBOX_BASE_URL}/v2/order/history?order_id=SB-1"),
    ]
    assert result["data"]["status"] == "cancelled"


def test_positions_normalize_provider_list(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse(
            {
                "status": "success",
                "data": [
                    {
                        "trading_symbol": "ITC",
                        "quantity": 5,
                        "average_price": 450.0,
                    }
                ],
            }
        )

    monkeypatch.setattr(sandbox, "urlopen", fake_urlopen)
    result = UpstoxSandboxClient("sandbox-secret").get_positions()

    assert result["data"]["positions"][0]["trading_symbol"] == "ITC"
    assert result["data"]["positions"][0]["quantity"] == 5


@pytest.mark.integration
def test_real_upstox_sandbox_order_lifecycle():
    """Opt-in provider validation through the official SDK; never runs in normal CI.

    Required environment:
      UPSTOX_SANDBOX_ACCESS_TOKEN
      UPSTOX_SANDBOX_INSTRUMENT_TOKEN
      UPSTOX_SANDBOX_PRICE

    UPSTOX_SANDBOX_CONFIRM=YES is additionally required before any order
    placement is attempted.

    The current Upstox sandbox capability list explicitly covers order
    placement and cancellation. Position APIs are not required by this
    sandbox evidence test. The official SDK client forces sandbox mode.
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
    from execution.engine import OrderRequest, OrderSide, OrderStatus, OrderType

    client = UpstoxSDKSandboxClient(token)

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
