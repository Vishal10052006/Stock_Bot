"""Upstox REST instrument-search transport.

This client performs read-only instrument discovery. It is intentionally
separate from order submission and accepts the access token supplied by the
caller. No order or account mutation is performed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from execution.adapters.upstox_instruments import InstrumentSearchClient


class UpstoxInstrumentSearchError(RuntimeError):
    """Raised when the Upstox instrument-search request fails."""


@dataclass(frozen=True, slots=True)
class UpstoxInstrumentSearchClient(InstrumentSearchClient):
    access_token: str
    base_url: str = "https://api.upstox.com"
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.access_token.strip():
            raise ValueError("access_token must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")

    def search_instruments(
        self,
        query: str,
        *,
        exchange: str = "NSE",
        segment: str = "EQ",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if limit <= 0:
            raise ValueError("limit must be positive")

        params = urlencode(
            {
                "query": normalized_query,
                "exchanges": exchange.strip().upper(),
                "segments": segment.strip().upper(),
                "records": str(limit),
            }
        )
        request = Request(
            f"{self.base_url.rstrip('/')}/v2/instruments/search?{params}",
            method="GET",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}",
            },
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise UpstoxInstrumentSearchError(
                f"Upstox instrument-search HTTP {exc.code}: {detail[:500]}"
            ) from exc
        except URLError as exc:
            raise UpstoxInstrumentSearchError(
                f"Upstox instrument-search transport error: {exc.reason}"
            ) from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise UpstoxInstrumentSearchError(
                "Upstox instrument-search returned non-JSON data"
            ) from exc

        if not isinstance(payload, dict):
            raise UpstoxInstrumentSearchError(
                "Upstox instrument-search response must be a JSON object"
            )

        data = payload.get("data")
        if not isinstance(data, list):
            raise UpstoxInstrumentSearchError(
                "Upstox instrument-search response data must be a list"
            )

        return [record for record in data if isinstance(record, dict)]


__all__ = [
    "UpstoxInstrumentSearchClient",
    "UpstoxInstrumentSearchError",
]
