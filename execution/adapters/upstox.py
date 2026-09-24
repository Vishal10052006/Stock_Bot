"""Phase 25 sandbox-first Upstox broker adapter boundary."""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any, Protocol
from execution.engine import OrderRequest, OrderSnapshot, OrderStatus, OrderType, PositionSnapshot
from execution.instruments import InstrumentResolver

@dataclass(frozen=True, slots=True)
class UpstoxAdapterConfig:
    api_base_url: str = "https://api-hft.upstox.com"
    access_token_env: str = "UPSTOX_ACCESS_TOKEN"
    sandbox: bool = True
    enabled: bool = False
    product: str = "D"
    validity: str = "DAY"
    slice_orders: bool = False
    market_protection: int = -1
    def __post_init__(self):
        if not self.api_base_url.strip() or not self.access_token_env.strip():
            raise ValueError("Upstox endpoints/env must be non-empty")
        if self.product not in {"I","D","MTF"}:
            raise ValueError("unsupported Upstox product")
        if self.validity not in {"DAY","IOC"}:
            raise ValueError("unsupported Upstox validity")
        if self.market_protection < -1 or self.market_protection > 25:
            raise ValueError("invalid market protection")
        if not isinstance(self.sandbox,bool) or not isinstance(self.enabled,bool):
            raise TypeError("sandbox and enabled must be bool")
        if self.enabled and not self.sandbox:
            raise ValueError("live Upstox adapter remains locked; sandbox=True is required")

class UpstoxClient(Protocol):
    def place_order_v3(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_order(self, order_id: str) -> dict[str, Any]: ...
    def cancel_order(self, order_id: str) -> dict[str, Any]: ...
    def positions(self) -> dict[str, Any]: ...

def _status(value: str) -> OrderStatus:
    mapping={
        "PUT_ORDER_REQ_RECEIVED":OrderStatus.SUBMITTED,
        "VALIDATION_PENDING":OrderStatus.SUBMITTED,
        "OPEN":OrderStatus.OPEN,
        "PARTIALLY_FILLED":OrderStatus.PARTIALLY_FILLED,
        "COMPLETE":OrderStatus.FILLED,
        "FILLED":OrderStatus.FILLED,
        "CANCELLED":OrderStatus.CANCELLED,
        "REJECTED":OrderStatus.REJECTED_BROKER,
        "EXPIRED":OrderStatus.EXPIRED,
    }
    return mapping.get(value.strip().upper().replace(" ","_"),OrderStatus.UNKNOWN)

class UpstoxBrokerAdapter:
    VERSION="UPSTOX-ADAPTER-v1.1"
    def __init__(self, config: UpstoxAdapterConfig, client: UpstoxClient | None = None, instrument_resolver: InstrumentResolver | None = None):
        self.config=config
        self.client=client
        self.instrument_resolver=instrument_resolver
        self._broker_order_ids: dict[str,str]={}

    def _require_enabled(self):
        if not self.config.enabled:
            raise RuntimeError("Upstox adapter is disabled")
        if not self.config.sandbox:
            raise RuntimeError("live Upstox adapter is locked")
        if self.client is None:
            raise RuntimeError("an explicitly supplied sandbox client is required")
        if self.instrument_resolver is None:
            raise RuntimeError("an explicit instrument resolver is required")

    def _payload(self, order: OrderRequest):
        if order.quantity != int(order.quantity):
            raise ValueError("Upstox quantity must be an integer")
        instrument=self.instrument_resolver.resolve(order.symbol)
        if order.quantity % instrument.lot_size != 0:
            raise ValueError("order quantity violates instrument lot size")
        return {
            "quantity":int(order.quantity),
            "product":self.config.product,
            "validity":self.config.validity,
            "price":0.0 if order.order_type is OrderType.MARKET else float(order.limit_price),
            "tag":order.client_order_id,
            "instrument_token":instrument.instrument_token,
            "order_type":order.order_type.value,
            "transaction_type":order.side.value,
            "disclosed_quantity":0,
            "trigger_price":0.0,
            "is_amo":False,
            "slice":self.config.slice_orders,
            "market_protection":self.config.market_protection,
        }

    @staticmethod
    def _data(response):
        if not isinstance(response,dict) or response.get("status")!="success":
            raise ValueError("invalid Upstox response")
        data=response.get("data")
        if not isinstance(data,dict):
            raise ValueError("Upstox response data must be an object")
        return data

    def submit(self, order):
        self._require_enabled()
        if order.client_order_id in self._broker_order_ids:
            broker_id=self._broker_order_ids[order.client_order_id]
            data=self._data(self.client.get_order(broker_id))
            return self._snapshot(data,order.client_order_id)
        data=self._data(self.client.place_order_v3(self._payload(order)))
        ids=data.get("order_ids")
        if not isinstance(ids,list) or not ids or not all(isinstance(x,str) and x.strip() for x in ids):
            raise ValueError("Upstox place response must contain order_ids")
        broker_id=ids[0]
        self._broker_order_ids[order.client_order_id]=broker_id
        return OrderSnapshot(broker_order_id=broker_id,client_order_id=order.client_order_id,status=OrderStatus.SUBMITTED,requested_quantity=order.quantity,reason="Upstox sandbox order accepted")

    def _snapshot(self,data,client_order_id):
        qty=float(data.get("quantity"))
        filled=float(data.get("filled_quantity",data.get("filled_qty",0.0)))
        avg=data.get("average_price",data.get("average_fill_price"))
        avg=None if avg in (None,0,0.0) and filled==0 else float(avg)
        broker_id=str(data.get("order_id","")).strip()
        if not broker_id:
            raise ValueError("Upstox order response must contain order_id")
        self._broker_order_ids.setdefault(client_order_id,broker_id)
        return OrderSnapshot(broker_order_id=broker_id,client_order_id=client_order_id,status=_status(str(data.get("status","UNKNOWN"))),requested_quantity=qty,filled_quantity=filled,average_fill_price=avg,reason=str(data.get("status_message","")))

    def get_order(self, client_order_id):
        self._require_enabled()
        broker_id=self._broker_order_ids.get(client_order_id)
        if broker_id is None:
            raise RuntimeError("broker order identity is unavailable; reconcile by provider order history before refresh")
        return self._snapshot(self._data(self.client.get_order(broker_id)),client_order_id)

    def cancel(self, client_order_id):
        self._require_enabled()
        current=self.get_order(client_order_id)
        self._data(self.client.cancel_order(current.broker_order_id))
        return OrderSnapshot(broker_order_id=current.broker_order_id,client_order_id=client_order_id,status=OrderStatus.CANCELLED,requested_quantity=current.requested_quantity,filled_quantity=current.filled_quantity,average_fill_price=current.average_fill_price,reason="Upstox sandbox cancellation accepted")

    def positions(self):
        self._require_enabled()
        data=self._data(self.client.positions())
        rows=data.get("net_positions",data.get("positions",[]))
        if not isinstance(rows,list):
            raise ValueError("Upstox positions must be a list")
        result=[]
        for row in rows:
            if not isinstance(row,dict):
                raise ValueError("invalid Upstox position")
            symbol=str(row.get("trading_symbol") or row.get("instrument_token") or "").strip()
            quantity=float(row.get("quantity",row.get("net_quantity",0.0)))
            price=float(row.get("average_price",row.get("avg_price",0.0)))
            if not symbol or not math.isfinite(quantity) or not math.isfinite(price) or price<=0:
                raise ValueError("invalid Upstox position values")
            result.append(PositionSnapshot(symbol,quantity,price))
        return tuple(result)
