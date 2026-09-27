"""Opt-in production Upstox position evidence runner.

Only the read-only Get Positions endpoint is called. The access token is
supplied by the caller and is never included in returned error text.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from execution.adapters.upstox_positions import fetch_upstox_positions


PRODUCTION_POSITIONS_URL = "https://api.upstox.com/v2/portfolio/short-term-positions"


class UpstoxProductionPositionClient:
    """Minimal read-only transport for the documented production positions API."""

    def __init__(self, access_token: str, *, timeout_seconds: float = 15.0) -> None:
        if not access_token.strip():
            raise ValueError("access_token must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._access_token = access_token
        self._timeout_seconds = timeout_seconds

    def get_positions(self) -> dict[str, Any]:
        """Fetch current positions; never places or modifies orders."""
        request = Request(
            PRODUCTION_POSITIONS_URL,
            method="GET",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._access_token}",
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise RuntimeError(f"Upstox positions HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("Upstox positions transport failure") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Upstox positions returned non-JSON data") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Upstox positions response must be an object")
        return decoded


__all__ = ["PRODUCTION_POSITIONS_URL", "UpstoxProductionPositionClient"]
