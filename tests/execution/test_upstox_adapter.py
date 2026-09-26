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
