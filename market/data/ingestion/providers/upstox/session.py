"""Secure Upstox provider session boundary."""

from __future__ import annotations

from dataclasses import dataclass

from .auth import get_authorized_websocket_uri
from .config import UpstoxFeedConfig


@dataclass(frozen=True, slots=True)
class UpstoxMarketDataSession:
    """Authorized, non-ordering session for Upstox Market Data V3."""

    config: UpstoxFeedConfig
    websocket_uri: str

    @classmethod
    def authorize(
        cls,
        config: UpstoxFeedConfig | None = None,
    ) -> "UpstoxMarketDataSession":
        """Authorize one market-data WebSocket session.

        This method performs authorization only. It never submits, modifies,
        or cancels an order.
        """
        resolved = config or UpstoxFeedConfig.from_env()
        uri = get_authorized_websocket_uri(
            resolved.access_token,
            timeout_seconds=resolved.timeout_seconds,
        )
        return cls(config=resolved, websocket_uri=uri)

    def evidence(self) -> dict[str, object]:
        """Return non-secret session evidence."""
        return {
            "provider": "upstox",
            "environment": self.config.environment,
            "authorized": True,
            "market_data_only": True,
            "live_order_submission": False,
            "live_broker_order_submission": False,
            "websocket_uri_present": bool(self.websocket_uri),
        }


__all__ = ["UpstoxMarketDataSession"]
