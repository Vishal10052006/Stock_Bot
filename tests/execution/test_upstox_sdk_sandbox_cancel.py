from __future__ import annotations

from types import SimpleNamespace

from execution.adapters.upstox_sdk import UpstoxSDKSandboxClient


class FakeOrderV3:
    def cancel_order(self, order_id: str):
        return SimpleNamespace(
            to_dict=lambda: {"status": "success", "data": {"order_id": order_id}}
        )


class FakeOrder:
    def get_order_details(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("sandbox cancellation must not query order history")


class FakeSdk:
    class Configuration:
        def __init__(self, sandbox: bool):
            assert sandbox is True
            self.access_token = ""

    class ApiClient:
        def __init__(self, configuration):
            self.configuration = configuration

    OrderApiV3 = FakeOrderV3
    OrderApi = FakeOrder


def test_sandbox_cancel_uses_v3_acknowledgement_without_history():
    client = UpstoxSDKSandboxClient("sandbox-token", sdk_module=FakeSdk)
    result = client.cancel_order("SB-1")

    assert result == {"status": "success", "data": {"order_id": "SB-1"}}
