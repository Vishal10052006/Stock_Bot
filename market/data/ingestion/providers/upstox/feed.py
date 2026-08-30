"""Upstox Market Data Feed V3 adapter.

This module intentionally keeps provider-specific concerns behind the
provider-independent ``MarketFeed`` interface.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
import json
import uuid

from market.data.events import MarketEvent, MarketEventType
from market.data.ingestion import MarketFeed

from .auth import get_authorized_websocket_uri
from .config import UpstoxFeedConfig
from .instrument_mapper import UpstoxInstrumentMapper


class UpstoxMarketFeed(MarketFeed):
    """Provider adapter for Upstox Market Data Feed V3."""

    def __init__(
        self,
        config: UpstoxFeedConfig,
        instrument_mapper: UpstoxInstrumentMapper,
    ) -> None:
        """Store runtime configuration without opening a network connection."""
        self.config = config
        self.instrument_mapper = instrument_mapper
        self._ws = None
        self._subscribed_symbols: set[str] = set()

    @property
    def connected(self) -> bool:
        """Return whether a usable WebSocket is currently attached."""
        return self._ws is not None and not getattr(self._ws, "closed", False)

    def connect(self) -> None:
        """Authorize and open the provider WebSocket connection."""
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError(
                "websocket-client is required for the Upstox live feed"
            ) from exc

        uri = get_authorized_websocket_uri(
            self.config.access_token,
            timeout_seconds=self.config.timeout_seconds,
        )
        self._ws = websocket.create_connection(
            uri,
            timeout=self.config.timeout_seconds,
        )

    def subscribe(self, symbols: Iterable[str]) -> None:
        """Subscribe internal symbols using Upstox instrument keys."""
        normalized = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
        if not normalized:
            raise ValueError("at least one non-empty symbol is required")
        if not self.connected:
            raise RuntimeError("market feed must be connected before subscribing")

        instrument_keys = [
            self.instrument_mapper.instrument_key(symbol)
            for symbol in sorted(normalized)
        ]
        request = {
            "guid": str(uuid.uuid4()),
            "method": "sub",
            "data": {
                "mode": self.config.mode,
                "instrumentKeys": instrument_keys,
            },
        }
        # Upstox V3 requires the subscription request to be sent as bytes.
        self._ws.send(json.dumps(request).encode("utf-8"), opcode=websocket.ABNF.OPCODE_BINARY)
        self._subscribed_symbols.update(normalized)

    def events(self) -> Iterator[MarketEvent]:
        """Yield canonical events from LTPC/full provider messages.

        This first adapter milestone handles the common LTPC structure. More
        detailed quote/depth mapping belongs in later Phase 3 enhancements.
        """
        if not self.connected:
            raise RuntimeError("market feed must be connected before reading events")

        while True:
            raw_message = self._ws.recv()
            if raw_message is None:
                return

            if isinstance(raw_message, str):
                # V3 market updates are protobuf/binary. Ignore unexpected text
                # frames rather than attempting unsafe JSON interpretation.
                continue

            # Protobuf decoding is provider-specific and intentionally deferred
            # to the decoder boundary; callers can wire the generated module.
            raise NotImplementedError(
                "Wire the generated Upstox MarketDataFeedV3 protobuf decoder "
                "before consuming live events"
            )
            yield  # pragma: no cover

    def disconnect(self) -> None:
        """Close the active provider connection safely."""
        if self._ws is not None:
            self._ws.close()
        self._ws = None
