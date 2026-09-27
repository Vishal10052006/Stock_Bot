from __future__ import annotations

import pytest

from execution.adapters.upstox import UpstoxAdapterConfig, UpstoxBrokerAdapter
from execution.engine import (
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSnapshot,
)


class FakeUpstoxClient:
    def __init__(self) -> None:
        self.placed: list[dict] = []
        self.cancelled: list[str] = []
        self.orders: dict[str, dict] = {}
        self.positions_response = {"data": {"positions": []}}

    def place_order(self, payload):
        self.placed.append(payload)
        order_id = "UP-100"
        response = {
            "status": "success",
            "data": {
                "order_ids": [order_id],
                "order_id": order_id,
                "tag": payload["tag"],
                "quantity": payload["quantity"],
                "status": "complete",
                "filled_quantity": payload["quantity"],
                "average_price": 100.25,
            },
        }
        self.orders[payload["tag"]] = response
        return response

    def find_order_by_tag(self, tag):
        return self.orders.get(tag)

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        for response in self.orders.values():
            if response["data"].get("order_id") == order_id:
                response["data"]["status"] = "cancelled"
                return response
        raise KeyError(order_id)

    def get_positions(self):
        return self.positions_response


def order() -> OrderRequest:
    return OrderRequest(
        client_order_id="SB-TEST-ORDER-123456789",
        decision_id="decision-1",
        symbol="ITC",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )


def adapter(client: FakeUpstoxClient) -> UpstoxBrokerAdapter:
    return UpstoxBrokerAdapter(
        UpstoxAdapterConfig(
            api_base_url="https://api-hft.upstox.com",
            enabled=True,
            instrument_token_resolver=lambda symbol: f"NSE_EQ|{symbol}",
        ),
        client=client,
    )


def test_disabled_adapter_is_fail_closed():
    with pytest.raises(RuntimeError, match="disabled"):
        UpstoxBrokerAdapter(
            UpstoxAdapterConfig(api_base_url="https://api-hft.upstox.com"),
            client=FakeUpstoxClient(),
        ).submit(order())


def test_submit_maps_execution_request_to_upstox_payload():
    client = FakeUpstoxClient()
    result = adapter(client).submit(order())

    assert client.placed[0] == {
        "quantity": 10,
        "product": "D",
        "validity": "DAY",
        "price": 0.0,
        "tag": "SB-TEST-ORDER-123456789",
        "instrument_token": "NSE_EQ|ITC",
        "order_type": "MARKET",
        "transaction_type": "BUY",
        "disclosed_quantity": 0,
        "trigger_price": 0.0,
        "is_amo": False,
        "slice": False,
        "market_protection": -1,
    }
    assert result.broker_order_id == "UP-100"
    assert result.status is OrderStatus.FILLED
    assert result.filled_quantity == 10
    assert result.average_fill_price == 100.25


def test_fractional_quantity_is_rejected_without_truncation():
    fractional = OrderRequest(
        client_order_id="SB-TEST-FRACTIONAL",
        decision_id="decision-1",
        symbol="ITC",
        side=OrderSide.BUY,
        quantity=10.5,
        order_type=OrderType.MARKET,
    )
    with pytest.raises(ValueError, match="refusing to truncate"):
        adapter(FakeUpstoxClient()).submit(fractional)


def test_inconsistent_fill_quantity_is_rejected():
    client = FakeUpstoxClient()
    client.orders["bad-fill"] = {
        "data": {
            "order_id": "UP-BF",
            "tag": "bad-fill",
            "quantity": 100,
            "filled_quantity": 40,
            "status": "partially filled",
            "fills": [{"trade_id": "T1", "quantity": 30, "price": 101.0}],
        }
    }
    with pytest.raises(ValueError, match="fill quantity"):
        adapter(client).get_order("bad-fill")


def test_filled_status_requires_full_quantity():
    client = FakeUpstoxClient()
    client.orders["bad-filled"] = {
        "data": {
            "order_id": "UP-BF2",
            "tag": "bad-filled",
            "quantity": 100,
            "filled_quantity": 40,
            "status": "complete",
        }
    }
    with pytest.raises(ValueError, match="FILLED status"):
        adapter(client).get_order("bad-filled")


def test_partial_fill_and_rejection_mapping():
    client = FakeUpstoxClient()
    client.orders["partial"] = {
        "data": {
            "order_id": "UP-P",
            "tag": "partial",
            "quantity": 100,
            "filled_quantity": 40,
            "status": "partially filled",
            "average_price": 101.0,
        }
    }
    client.orders["rejected"] = {
        "data": {
            "order_id": "UP-R",
            "tag": "rejected",
            "quantity": 100,
            "filled_quantity": 0,
            "status": "rejected",
            "status_message": "instrument blocked",
        }
    }

    assert adapter(client).get_order("partial").status is OrderStatus.PARTIALLY_FILLED
    rejected = adapter(client).get_order("rejected")
    assert rejected.status is OrderStatus.REJECTED_BROKER
    assert rejected.reason == "instrument blocked"


def test_lookup_missing_order_is_none():
    assert adapter(FakeUpstoxClient()).get_order("missing") is None


def test_cancel_uses_broker_order_id():
    client = FakeUpstoxClient()
    adapter(client).submit(order())
    result = adapter(client).cancel(order().client_order_id)
    assert client.cancelled == ["UP-100"]
    assert result.status is OrderStatus.CANCELLED


def test_positions_map_to_signed_snapshots():
    client = FakeUpstoxClient()
    client.positions_response = {
        "data": {
            "positions": [
                {
                    "trading_symbol": "ITC",
                    "quantity": 25,
                    "average_price": 456.5,
                },
                {
                    "trading_symbol": "TCS",
                    "quantity": -5,
                    "average_price": 3010.0,
                },
            ]
        }
    }

    positions = adapter(client).positions()
    assert positions == (
        PositionSnapshot("ITC", 25, 456.5),
        PositionSnapshot("TCS", -5, 3010.0),
    )


# UPSTOX-08 hardening coverage

def test_positions_reject_non_mapping_entries():
    client = FakeUpstoxClient()
    client.positions_response = {"data": {"positions": ["invalid"]}}
    with pytest.raises(ValueError, match="position entry"):
        adapter(client).positions()


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("quantity", float("nan"), "quantity"),
        ("quantity", float("inf"), "quantity"),
        ("average_price", float("nan"), "average price"),
        ("average_price", float("inf"), "average price"),
    ],
)
def test_positions_reject_non_finite_numeric_fields(field, value, pattern):
    client = FakeUpstoxClient()
    client.positions_response = {
        "data": {
            "positions": [
                {
                    "trading_symbol": "ITC",
                    "quantity": 5 if field != "quantity" else value,
                    "average_price": 450.0 if field != "average_price" else value,
                }
            ]
        }
    }
    with pytest.raises(ValueError, match=pattern):
        adapter(client).positions()


def test_positions_reject_negative_average_price():
    client = FakeUpstoxClient()
    client.positions_response = {
        "data": {
            "positions": [
                {
                    "trading_symbol": "ITC",
                    "quantity": 5,
                    "average_price": -1.0,
                }
            ]
        }
    }
    with pytest.raises(ValueError, match="average price"):
        adapter(client).positions()


def test_positions_reject_malformed_numeric_values():
    client = FakeUpstoxClient()
    client.positions_response = {
        "data": {
            "positions": [
                {
                    "trading_symbol": "ITC",
                    "quantity": "not-a-number",
                    "average_price": 450.0,
                }
            ]
        }
    }
    with pytest.raises(ValueError, match="quantity"):
        adapter(client).positions()


def test_production_position_transport_normalizes_provider_response():
    from execution.adapters.upstox_positions import fetch_upstox_positions

    result = fetch_upstox_positions(
        lambda: {
            "status": "success",
            "data": [
                {
                    "trading_symbol": "ITC",
                    "quantity": 12,
                    "average_price": 455.25,
                },
                {
                    "trading_symbol": "TCS",
                    "quantity": -3,
                    "average_price": 3005.0,
                },
            ],
        }
    )

    assert result["status"] == "success"
    assert result["data"]["positions"][0]["trading_symbol"] == "ITC"
    assert result["data"]["positions"][1]["quantity"] == -3


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"status": "success", "data": {}},
        {"status": "success", "data": [{"trading_symbol": "ITC"}, "bad"]},
    ],
)
def test_production_position_transport_rejects_malformed_response(response):
    from execution.adapters.upstox_positions import (
        UpstoxPositionTransportError,
        fetch_upstox_positions,
    )

    with pytest.raises(UpstoxPositionTransportError):
        fetch_upstox_positions(lambda response=response: response)


def test_production_position_transport_wraps_provider_failure():
    from execution.adapters.upstox_positions import (
        UpstoxPositionTransportError,
        fetch_upstox_positions,
    )

    def failing_request():
        raise TimeoutError("provider timeout")

    with pytest.raises(UpstoxPositionTransportError, match="request failed"):
        fetch_upstox_positions(failing_request)


def test_injected_position_provider_reaches_adapter_contract():
    client = FakeUpstoxClient()
    client.positions_response = {"data": {"positions": []}}

    def provider():
        return {
            "status": "success",
            "data": [
                {
                    "trading_symbol": "ITC",
                    "quantity": 7,
                    "average_price": 452.5,
                }
            ],
        }

    configured = UpstoxAdapterConfig(
        api_base_url="https://api-hft.upstox.com",
        enabled=True,
        instrument_token_resolver=lambda symbol: f"NSE_EQ|{symbol}",
        position_provider=provider,
    )
    positions = UpstoxBrokerAdapter(configured, client=client).positions()

    assert positions == (PositionSnapshot("ITC", 7, 452.5),)
    assert client.positions_response["data"]["positions"] == []


def test_injected_position_provider_failure_propagates_without_fabricating_positions():
    client = FakeUpstoxClient()

    def failing_provider():
        raise RuntimeError("position provider unavailable")

    configured = UpstoxAdapterConfig(
        api_base_url="https://api-hft.upstox.com",
        enabled=True,
        instrument_token_resolver=lambda symbol: f"NSE_EQ|{symbol}",
        position_provider=failing_provider,
    )
    with pytest.raises(RuntimeError, match="provider unavailable"):
        UpstoxBrokerAdapter(configured, client=client).positions()


def test_production_position_client_uses_read_only_positions_endpoint(monkeypatch):
    from execution.adapters.upstox_production_positions import (
        PRODUCTION_POSITIONS_URL,
        UpstoxProductionPositionClient,
    )

    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"success","data":[]}'

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["method"] = request.method
        seen["auth"] = request.get_header("Authorization")
        return Response()

    monkeypatch.setattr(
        "execution.adapters.upstox_production_positions.urlopen",
        fake_urlopen,
    )

    result = UpstoxProductionPositionClient("real-token-for-test-only").get_positions()

    assert seen == {
        "url": PRODUCTION_POSITIONS_URL,
        "method": "GET",
        "auth": "Bearer real-token-for-test-only",
    }
    assert result == {"status": "success", "data": []}
