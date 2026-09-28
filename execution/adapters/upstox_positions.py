"""Upstox production-position transport boundary.

This module is deliberately separate from the sandbox SDK transport. It exposes
only the provider response contract required by UpstoxBrokerAdapter.positions.
Actual network construction remains caller-owned, so credentials and live
connectivity do not enter the execution engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable


class UpstoxPositionTransportError(RuntimeError):
    """Raised when a provider position response cannot be consumed safely."""


def fetch_upstox_positions(
    request: Callable[[], Mapping[str, Any]],
) -> dict[str, Any]:
    """Fetch and normalize an authoritative production position response.

    request is injected so tests can exercise the provider-response boundary
    without credentials or network calls.
    """
    try:
        response = request()
    except Exception as exc:
        raise UpstoxPositionTransportError(
            "Upstox position request failed"
        ) from exc

    if not isinstance(response, Mapping):
        raise UpstoxPositionTransportError(
            "Upstox position response must be an object"
        )

    data = response.get("data")
    if not isinstance(data, (list, tuple)):
        raise UpstoxPositionTransportError(
            "Upstox position response data must be a list"
        )

    records: list[dict[str, Any]] = []
    for record in data:
        if not isinstance(record, Mapping):
            raise UpstoxPositionTransportError(
                "Upstox position response contains a non-object record"
            )
        records.append(dict(record))

    return {
        "status": response.get("status", "success"),
        "data": {"positions": records},
    }


__all__ = ["UpstoxPositionTransportError", "fetch_upstox_positions"]
