"""Upstox Market Data Feed V3 adapter.

Provider-specific concerns stay behind the provider-independent MarketFeed
interface so the trading core remains broker/data-source agnostic.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
import importlib
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
        *,
        protobuf_module=None,
        websocket_module=None,
    ) -> None:
        """Store dependencies without opening a network connection."""
        self.config = config
        self.instrument_mapper = instrument_mapper
        self._protobuf_module = protobuf_module
        self._websocket = websocket_module
        self._ws = None
        self._subscribed_symbols: set[str] = set()

    @property
    def connected(self) -> bool:
        """Return whether a usable WebSocket connection is attached."""
        return self._ws is not None and not getattr(self._ws, "closed", False)

    def _load_websocket_module(self):
        """Load websocket-client lazily so imports stay testable."""
        if self._websocket is None:
            try:
                self._websocket = importlib.import_module("websocket")
            except ImportError as exc:
                raise RuntimeError(
                    "websocket-client is required for the Upstox live feed"
                ) from exc
        return self._websocket

    def connect(self) -> None:
        """Authorize and open the provider WebSocket connection."""
        websocket = self._load_websocket_module()
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

        websocket = self._load_websocket_module()
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
        # Upstox V3 expects the subscription request in binary form.
        self._ws.send(
            json.dumps(request).encode("utf-8"),
            opcode=websocket.ABNF.OPCODE_BINARY,
        )
        self._subscribed_symbols.update(normalized)

    def events(self) -> Iterator[MarketEvent]:
        """Yield canonical trade events from decoded LTPC feed messages."""
        if not self.connected:
            raise RuntimeError("market feed must be connected before reading events")
        if self._protobuf_module is None:
            raise RuntimeError(
                "A generated Upstox MarketDataFeedV3 protobuf module is required"
            )

        from .decoder import decode_feed_message, epoch_millis_to_datetime

        while True:
            received_timestamp = datetime.now().astimezone()
            raw_message = self._ws.recv()
            if raw_message is None:
                return
            if isinstance(raw_message, str):
                # V3 market updates are binary protobuf frames.
                continue

            decoded = decode_feed_message(raw_message, self._protobuf_module)
            feeds = getattr(decoded, "feeds", None)
            if not feeds:
                continue

            for instrument_key, feed in feeds.items():
                ltpc = getattr(feed, "ltpc", None)
                if ltpc is None or not hasattr(ltpc, "ltp"):
                    continue

                symbol = next(
                    (
                        candidate
                        for candidate in self._subscribed_symbols
                        if self.instrument_mapper.instrument_key(candidate) == instrument_key
                    ),
                    instrument_key,
                )
                event_timestamp = epoch_millis_to_datetime(getattr(ltpc, "ltt", 0))
                sequence = getattr(ltpc, "sequence_number", None)

                yield MarketEvent(
                    event_id=(
                        f"{instrument_key}:{getattr(ltpc, 'ltt', '0')}"
                        f":{getattr(ltpc, 'ltq', '0')}"
                    ),
                    symbol=symbol,
                    exchange="NSE",
                    event_type=MarketEventType.TRADE,
                    price=float(ltpc.ltp),
                    volume=float(getattr(ltpc, "ltq", 0)),
                    exchange_timestamp=event_timestamp,
                    received_timestamp=received_timestamp,
                    sequence_number=sequence,
                )

    def disconnect(self) -> None:
        """Close the active provider connection safely."""
        if self._ws is not None:
            self._ws.close()
        self._ws = None
        self._subscribed_symbols.clear()
