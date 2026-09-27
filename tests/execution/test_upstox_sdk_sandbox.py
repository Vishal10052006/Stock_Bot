from __future__ import annotations

import os
import uuid

import pytest

from execution.adapters.upstox_sdk import UpstoxSDKError, UpstoxSDKSandboxClient


class FakeConfiguration:
    def __init__(self, *, sandbox: bool = False) -> None:
        self.sandbox = sandbox
        self.access_token = None


class FakeApiClient:
    def __init__(self, configuration) -> None:
        self.configuration = configuration


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def to_dict(self):
        return self._payload


class FakePlaceOrderV3Request:
    def __init__(self, **kwargs) -> None:
        self.payload = kwargs


class FakeOrderApiV3:
    def __init__(self, client) -> None:
        self.client = client
        self.placed = []
        self.cancelled = []

    def place_order(self, body):
        self.placed.append(body.payload)
        return FakeResponse(
            {
                "status": "success",
                "data": {"order_ids": ["SDK-1"]},
            }
        )

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        return FakeResponse({"status": "success", "data": {"order_id": order_id}})


class FakeOrderApi:
    def __init__(self, client) -> None:
        self.client = client
        self.history = [
            {"order_id": "SDK-1", "tag": "SDK-TAG", "quantity": 1, "status": "open"}
        ]

    def get_order_details(self, api_version, **kwargs):
        assert api_version == "2.0"
        if "order_id" in kwargs:
            return FakeResponse({"status": "success", "data": self.history})
        assert kwargs["tag"] == "SDK-TAG"
        return FakeResponse({"status": "success", "data": self.history})


class FakeSDK:
    Configuration = FakeConfiguration
    ApiClient = FakeApiClient
    OrderApiV3 = FakeOrderApiV3
    OrderApi = FakeOrderApi
    PlaceOrderV3Request = FakePlaceOrderV3Request


def test_sdk_client_forces_official_sandbox_configuration():
    client = UpstoxSDKSandboxClient("sandbox-token", sdk_module=FakeSDK)
    assert client._order_v3.client.configuration.sandbox is True
    assert client._order_v3.client.configuration.access_token == "sandbox-token"


def test_place_lookup_and_cancel_use_sdk_contract():
    client = UpstoxSDKSandboxClient("sandbox-token", sdk_module=FakeSDK)
    payload = {
        "quantity": 1,
        "product": "D",
        "validity": "DAY",
        "price": 100.0,
        "tag": "SDK-TAG",
        "instrument_token": "NSE_EQ|TEST",
        "order_type": "LIMIT",
        "transaction_type": "BUY",
        "disclosed_quantity": 0,
        "trigger_price": 0.0,
        "is_amo": False,
        "slice": False,
        "market_protection": -1,
    }

    placed = client.place_order(payload)
    assert placed["data"]["order_id"] == "SDK-1"
    assert placed["data"]["tag"] == "SDK-TAG"
    assert placed["data"]["quantity"] == 1

    looked_up = client.find_order_by_tag("SDK-TAG")
    assert looked_up is not None
    assert looked_up["data"]["order_id"] == "SDK-1"

    cancelled = client.cancel_order("SDK-1")
    assert cancelled["data"]["order_id"] == "SDK-1"
    assert client._order_v3.cancelled == ["SDK-1"]


def test_positions_are_explicitly_unsupported_in_sandbox():
    client = UpstoxSDKSandboxClient("sandbox-token", sdk_module=FakeSDK)
    with pytest.raises(UpstoxSDKError, match="position API"):
        client.get_positions()


def test_empty_token_is_rejected():
    with pytest.raises(ValueError, match="access_token"):
        UpstoxSDKSandboxClient("", sdk_module=FakeSDK)


def test_sdk_errors_are_normalized():
    class BrokenOrderApiV3(FakeOrderApiV3):
        def place_order(self, body):
            raise RuntimeError("provider unavailable")

    class BrokenSDK(FakeSDK):
        OrderApiV3 = BrokenOrderApiV3

    client = UpstoxSDKSandboxClient("sandbox-token", sdk_module=BrokenSDK)
    with pytest.raises(UpstoxSDKError, match="provider unavailable"):
        client.place_order({"quantity": 1})


@pytest.mark.integration
def test_real_upstox_sandbox_authentication_without_order_placement():
    """Validate a real sandbox token through an authenticated read-only request.

    Required environment:
      UPSTOX_SANDBOX_ACCESS_TOKEN
      UPSTOX_SANDBOX_AUTH_CONFIRM=YES

    This test deliberately does not place, modify, or cancel an order.
    """
    token = os.getenv("UPSTOX_SANDBOX_ACCESS_TOKEN")
    if not token:
        pytest.skip("Set UPSTOX_SANDBOX_ACCESS_TOKEN for real sandbox auth validation.")
    if os.getenv("UPSTOX_SANDBOX_AUTH_CONFIRM") != "YES":
        pytest.skip("Set UPSTOX_SANDBOX_AUTH_CONFIRM=YES to opt into provider authentication.")

    placeholder = {"YOUR_REAL_SANDBOX_TOKEN", "sandbox-token"}
    if token.strip() in placeholder:
        pytest.fail("Real sandbox authentication was enabled with a placeholder token.")

    client = UpstoxSDKSandboxClient(token)
    # A random tag makes this a read-only lookup and avoids relying on an
    # existing order. A successful authenticated response is sufficient to
    # distinguish transport/authentication success from an invalid token.
    result = client.find_order_by_tag(f"SB-AUTH-{uuid.uuid4().hex}")
    assert result is None or isinstance(result, dict)
