"""Official Upstox Python SDK sandbox transport.

This module is deliberately sandbox-only. It keeps SDK construction and
provider-specific response handling outside the execution engine while
preserving the existing UpstoxBrokerAdapter client contract.

The official SDK documents Configuration(sandbox=True) as the supported
sandbox mode. No live configuration or live base URL is accepted here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import import_module
from typing import Any


class UpstoxSDKError(RuntimeError):
    """Raised when the official Upstox SDK sandbox transport fails."""


class UpstoxSDKSandboxClient:
    """Adapter-facing transport backed by the official Upstox Python SDK."""

    def __init__(
        self,
        access_token: str,
        *,
        sdk_module: Any | None = None,
    ) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")

        self._sdk = sdk_module or import_module("upstox_client")
        try:
            configuration = self._sdk.Configuration(sandbox=True)
            configuration.access_token = access_token
            api_client = self._sdk.ApiClient(configuration)
            self._order_v3 = self._sdk.OrderApiV3(api_client)
            self._order_v2 = self._sdk.OrderApi(api_client)
        except Exception as exc:  # SDK construction errors must cross our boundary consistently.
            raise UpstoxSDKError("failed to initialize Upstox SDK sandbox client") from exc

    @staticmethod
    def _primitive(value: Any) -> Any:
        """Convert SDK model objects into plain Python containers."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Mapping):
            return {str(key): UpstoxSDKSandboxClient._primitive(item) for key, item in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [UpstoxSDKSandboxClient._primitive(item) for item in value]
        if hasattr(value, "to_dict"):
            return UpstoxSDKSandboxClient._primitive(value.to_dict())
        if hasattr(value, "__dict__"):
            return {
                str(key): UpstoxSDKSandboxClient._primitive(item)
                for key, item in vars(value).items()
                if not str(key).startswith("_")
            }
        return value

    @classmethod
    def _response(cls, response: Any) -> dict[str, Any]:
        primitive = cls._primitive(response)
        if not isinstance(primitive, dict):
            raise UpstoxSDKError("Upstox SDK response must be an object")
        return primitive

    @staticmethod
    def _raise(exc: Exception) -> None:
        detail = str(exc).strip()
        raise UpstoxSDKError(
            f"Upstox SDK sandbox request failed{': ' + detail if detail else ''}"
        ) from exc

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Place an order through the SDK's sandbox-enabled V3 API."""
        try:
            body = self._sdk.PlaceOrderV3Request(**payload)
            response = self._order_v3.place_order(body)
        except Exception as exc:
            self._raise(exc)

        result = self._response(response)
        data = result.get("data")
        if not isinstance(data, dict):
            raise UpstoxSDKError("Upstox SDK place-order response has invalid data")

        enriched = dict(data)
        order_ids = enriched.get("order_ids")
        if not enriched.get("order_id") and isinstance(order_ids, list) and order_ids:
            enriched["order_id"] = order_ids[0]
        enriched.setdefault("tag", payload.get("tag"))
        enriched.setdefault("quantity", payload.get("quantity"))
        enriched.setdefault("status", "put order req received")
        return {"status": result.get("status", "success"), "data": enriched}

    def find_order_by_tag(self, tag: str) -> dict[str, Any] | None:
        """Resolve the latest order-history record associated with a tag."""
        try:
            response = self._order_v2.get_order_details("2.0", tag=tag)
        except Exception as exc:
            self._raise(exc)

        result = self._response(response)
        raw = result.get("data")
        if not isinstance(raw, list) or not raw:
            return None

        records = [record for record in raw if isinstance(record, dict)]
        if not records:
            return None
        latest = dict(records[-1])
        latest["tag"] = latest.get("tag") or tag
        return {"status": result.get("status", "success"), "data": latest}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an order through the SDK V3 API, then return broker history."""
        try:
            self._order_v3.cancel_order(order_id)
            response = self._order_v2.get_order_details("2.0", order_id=order_id)
        except Exception as exc:
            self._raise(exc)

        result = self._response(response)
        raw = result.get("data")
        if not isinstance(raw, list) or not raw:
            raise UpstoxSDKError(
                f"cancel succeeded but order history is unavailable: {order_id}"
            )
        records = [record for record in raw if isinstance(record, dict)]
        if not records:
            raise UpstoxSDKError(
                f"cancel succeeded but order history contains no record: {order_id}"
            )
        return {"status": result.get("status", "success"), "data": dict(records[-1])}

    def get_positions(self) -> dict[str, Any]:
        """Reject sandbox position queries until Upstox exposes them in sandbox."""
        raise UpstoxSDKError(
            "Upstox sandbox does not currently expose a supported position API; "
            "position reconciliation requires separate provider evidence."
        )


__all__ = ["UpstoxSDKError", "UpstoxSDKSandboxClient"]
