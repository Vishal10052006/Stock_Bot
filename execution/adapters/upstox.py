"""Upstox broker adapter boundary.

The adapter contains only provider request/response mapping. Credentials and
HTTP client construction remain outside the execution domain. The adapter is
disabled by default and therefore remains fail-closed until provider-specific
validation is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from execution.adapters.base import BrokerAdapter
from execution.engine import (
    Fill,
    OrderRequest,
    OrderSnapshot,
    OrderStatus,
    PositionSnapshot,
)


@dataclass(frozen=True, slots=True)
class UpstoxAdapterConfig:
    """Provider configuration and deterministic request defaults."""

    api_base_url: str
    access_token_env: str = "UPSTOX_ACCESS_TOKEN"
    enabled: bool = False
    product: str = "D"
    validity: str = "DAY"
    slice: bool = False
    market_protection: int = -1
    instrument_token_resolver: Callable[[str], str] | None = None

    def __post_init__(self) -> None:
        if not self.api_base_url.strip():
            raise ValueError("api_base_url must not be empty")
        if not self.access_token_env.strip():
            raise ValueError("access_token_env must not be empty")
        if self.product not in {"I", "D", "MTF"}:
            raise ValueError("product must be I, D, or MTF")
        if self.validity not in {"DAY", "IOC"}:
            raise ValueError("validity must be DAY or IOC")
        if not -1 <= self.market_protection <= 25:
            raise ValueError("market_protection must be between -1 and 25")


class UpstoxBrokerAdapter(BrokerAdapter):
    """Map broker-neutral execution contracts to an injected Upstox client."""

    def __init__(self, config: UpstoxAdapterConfig, client: Any | None = None) -> None:
        self.config = config
        self.client = client

    def _require_enabled(self) -> None:
        if not self.config.enabled:
            raise RuntimeError(
                "Upstox live adapter is disabled; enable only after controlled "
                "validation and current broker/compliance verification."
            )
        if self.client is None:
            raise RuntimeError(
                "No Upstox client was supplied. Credentials/client construction "
                "must remain outside the execution domain."
            )

    @staticmethod
    def _data(response: Mapping[str, Any]) -> Mapping[str, Any]:
        data = response.get("data", response)
        if not isinstance(data, Mapping):
            raise ValueError("Upstox response data must be an object")
        return data

    @staticmethod
    def _status(value: Any) -> OrderStatus:
        normalized = str(value or "").strip().lower().replace("_", " ")
        mapping = {
            "put order req received": OrderStatus.SUBMITTED,
            "validation pending": OrderStatus.SUBMITTED,
            "open": OrderStatus.OPEN,
            "open pending": OrderStatus.OPEN,
            "trigger pending": OrderStatus.OPEN,
            "partially filled": OrderStatus.PARTIALLY_FILLED,
            "partial": OrderStatus.PARTIALLY_FILLED,
            "complete": OrderStatus.FILLED,
            "completed": OrderStatus.FILLED,
            "filled": OrderStatus.FILLED,
            "cancel pending": OrderStatus.CANCEL_PENDING,
            "cancelled": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED_BROKER,
            "expired": OrderStatus.EXPIRED,
        }
        try:
            return mapping[normalized]
        except KeyError as exc:
            raise ValueError(f"unsupported Upstox order status: {value!r}") from exc

    @staticmethod
    def _fill_tuple(
        data: Mapping[str, Any],
        client_order_id: str,
    ) -> tuple[Fill, ...]:
        raw_fills = data.get("fills") or data.get("trades") or ()
        if not isinstance(raw_fills, (list, tuple)):
            return ()

        fills: list[Fill] = []
        for index, raw in enumerate(raw_fills):
            if not isinstance(raw, Mapping):
                continue
            quantity = float(
                raw.get("quantity", raw.get("fill_quantity", raw.get("filled_quantity", 0)))
            )
            price = float(raw.get("price", raw.get("fill_price", 0)))
            if quantity <= 0 or price <= 0:
                continue
            fill_id = str(raw.get("fill_id") or raw.get("trade_id") or f"{client_order_id}-F{index}")
            fills.append(
                Fill(
                    fill_id=fill_id,
                    client_order_id=client_order_id,
                    quantity=quantity,
                    price=price,
                    fee=float(raw.get("fee", 0.0)),
                )
            )
        return tuple(fills)

    def _snapshot(
        self,
        response: Mapping[str, Any],
        *,
        client_order_id: str | None = None,
    ) -> OrderSnapshot:
        data = self._data(response)
        raw_ids = data.get("order_ids")
        first_id = raw_ids[0] if isinstance(raw_ids, (list, tuple)) and raw_ids else None
        broker_order_id = str(data.get("order_id") or first_id or "")
        tag = str(data.get("tag") or client_order_id or "")
        if not broker_order_id:
            raise ValueError("Upstox response missing order_id")
        if not tag:
            raise ValueError("Upstox response missing order tag")

        requested = float(data.get("quantity", data.get("requested_quantity", 0)))
        filled = float(data.get("filled_quantity", data.get("filled_qty", 0)))
        if requested <= 0:
            raise ValueError("Upstox response missing positive quantity")

        fills = self._fill_tuple(data, tag)
        average = data.get("average_price", data.get("average_fill_price"))
        if average is None and fills:
            total_qty = sum(fill.quantity for fill in fills)
            average = (
                sum(fill.quantity * fill.price for fill in fills) / total_qty
                if total_qty
                else None
            )

        return OrderSnapshot(
            broker_order_id=broker_order_id,
            client_order_id=tag,
            status=self._status(data.get("status")),
            requested_quantity=requested,
            filled_quantity=filled,
            average_fill_price=float(average) if average is not None else None,
            reason=str(data.get("status_message") or data.get("reason") or ""),
            fills=fills,
        )

    def _payload(self, order: OrderRequest) -> dict[str, Any]:
        resolver = self.config.instrument_token_resolver
        if resolver is None:
            raise ValueError("instrument_token_resolver is required for Upstox orders")
        instrument_token = resolver(order.symbol)
        if not instrument_token.strip():
            raise ValueError("instrument token resolver returned an empty token")

        return {
            "quantity": int(order.quantity),
            "product": self.config.product,
            "validity": self.config.validity,
            "price": float(order.limit_price or 0.0),
            "tag": order.client_order_id,
            "instrument_token": instrument_token,
            "order_type": order.order_type.value,
            "transaction_type": order.side.value,
            "disclosed_quantity": 0,
            "trigger_price": 0.0,
            "is_amo": False,
            "slice": self.config.slice,
            "market_protection": self.config.market_protection,
        }

    def submit(self, order: OrderRequest) -> OrderSnapshot:
        self._require_enabled()
        return self._snapshot(
            self.client.place_order(self._payload(order)),
            client_order_id=order.client_order_id,
        )

    def get_order(self, client_order_id: str) -> OrderSnapshot | None:
        self._require_enabled()
        response = self.client.find_order_by_tag(client_order_id)
        if response is None:
            return None
        return self._snapshot(response, client_order_id=client_order_id)

    def cancel(self, client_order_id: str) -> OrderSnapshot:
        self._require_enabled()
        current = self.client.find_order_by_tag(client_order_id)
        if current is None:
            raise KeyError(f"Upstox order not found: {client_order_id}")
        current_data = self._data(current)
        order_id = str(current_data.get("order_id") or "")
        if not order_id:
            raise ValueError("Upstox order lookup missing order_id")
        return self._snapshot(
            self.client.cancel_order(order_id),
            client_order_id=client_order_id,
        )

    def positions(self) -> tuple[PositionSnapshot, ...]:
        self._require_enabled()
        response = self.client.get_positions()
        data = self._data(response)
        raw_positions = data.get("positions", ())
        if not isinstance(raw_positions, (list, tuple)):
            raise ValueError("Upstox positions response must contain a list")

        positions: list[PositionSnapshot] = []
        for raw in raw_positions:
            if not isinstance(raw, Mapping):
                continue
            symbol = str(raw.get("trading_symbol") or raw.get("symbol") or "")
            if not symbol:
                raise ValueError("Upstox position missing trading symbol")
            quantity = float(raw.get("quantity", raw.get("net_quantity", 0)))
            average = float(raw.get("average_price", raw.get("average_buy_price", 0)))
            positions.append(PositionSnapshot(symbol, quantity, average))
        return tuple(positions)


__all__ = ["UpstoxAdapterConfig", "UpstoxBrokerAdapter"]
