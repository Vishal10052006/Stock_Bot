"""Minimal, sandbox-only Upstox HTTP client.

This module deliberately has no live-provider mode. It uses the dedicated
Upstox sandbox host and accepts a sandbox access token supplied by the caller.
The execution domain still owns request/response mapping in UpstoxBrokerAdapter;
this client owns only transport and provider lookup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SANDBOX_BASE_URL = "https://sandbox.upstox.com"
_SANDBOX_HOST = "sandbox.upstox.com"


class UpstoxSandboxError(RuntimeError):
    """Raised when a sandbox request cannot be completed."""


@dataclass(frozen=True, slots=True)
class UpstoxSandboxClient:
    """Small transport client restricted to the Upstox sandbox host."""

    access_token: str
    base_url: str = SANDBOX_BASE_URL
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.access_token.strip():
            raise ValueError("access_token must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.base_url.rstrip("/") != SANDBOX_BASE_URL:
            raise ValueError(
                "UpstoxSandboxClient only permits https://sandbox.upstox.com"
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query)}"

        request = Request(
            url,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise UpstoxSandboxError(
                f"Upstox sandbox HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except URLError as exc:
            raise UpstoxSandboxError(
                f"Upstox sandbox transport error: {exc.reason}"
            ) from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise UpstoxSandboxError("Upstox sandbox returned non-JSON data") from exc

        if not isinstance(decoded, dict):
            raise UpstoxSandboxError("Upstox sandbox response must be a JSON object")
        return decoded

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Place an order through the sandbox V2 endpoint."""
        response = self._request("POST", "/v2/order/place", payload=payload)
        data = response.get("data")
        if not isinstance(data, dict):
            raise UpstoxSandboxError("sandbox place-order response has invalid data")

        enriched = dict(data)
        enriched.setdefault("order_id", data.get("order_id"))
        enriched.setdefault("tag", payload.get("tag"))
        enriched.setdefault("quantity", payload.get("quantity"))
        enriched.setdefault("status", "put order req received")
        return {"status": response.get("status", "success"), "data": enriched}

    def find_order_by_tag(self, tag: str) -> dict[str, Any] | None:
        """Resolve the latest order state by the deterministic Upstox tag."""
        response = self._request("GET", "/v2/order/history", query={"tag": tag})
        raw = response.get("data")
        if not isinstance(raw, list) or not raw:
            return None

        records = [record for record in raw if isinstance(record, dict)]
        if not records:
            return None

        latest = dict(records[-1])
        latest["tag"] = latest.get("tag") or tag
        return {"status": response.get("status", "success"), "data": latest}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open/pending sandbox order and return its latest state."""
        self._request("DELETE", "/v2/order/cancel", query={"order_id": order_id})
        latest = self._request(
            "GET",
            "/v2/order/history",
            query={"order_id": order_id},
        )
        raw = latest.get("data")
        if not isinstance(raw, list) or not raw:
            raise UpstoxSandboxError(
                f"cancel succeeded but order history is unavailable: {order_id}"
            )
        records = [record for record in raw if isinstance(record, dict)]
        if not records:
            raise UpstoxSandboxError(
                f"cancel succeeded but order history contains no record: {order_id}"
            )
        return {"status": latest.get("status", "success"), "data": dict(records[-1])}

    def get_positions(self) -> dict[str, Any]:
        """Return positions normalized to the adapter's expected container."""
        response = self._request("GET", "/v2/portfolio/short-term-positions")
        raw = response.get("data")
        if not isinstance(raw, list):
            raise UpstoxSandboxError("sandbox positions response data must be a list")
        return {"status": response.get("status", "success"), "data": {"positions": raw}}


__all__ = [
    "SANDBOX_BASE_URL",
    "UpstoxSandboxClient",
    "UpstoxSandboxError",
]
