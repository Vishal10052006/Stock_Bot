"""Upstox Market Data Feed V3 adapter.

Provider-specific concerns stay behind the provider-independent MarketFeed
interface so the trading core remains broker/data-source agnostic.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
import importlib
import json
import time
import uuid

from market.data.events import MarketEvent, MarketEventType
from market.data.ingestion import MarketFeed

from market.data.metrics import DataQualityMetrics
from market.data.validation import MarketEventValidator

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
        event_validator: MarketEventValidator | None = None,
        metrics: DataQualityMetrics | None = None,
    ) -> None:
        """Store dependencies without opening a network connection."""
        self.config = config
        self.instrument_mapper = instrument_mapper
        self._protobuf_module = protobuf_module
        self._websocket = websocket_module
        self._ws = None
        self._subscribed_symbols: set[str] = set()
        self.event_validator = event_validator
        self.metrics = metrics

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

    def _open_connection(self) -> None:
        """Authorize and open one WebSocket connection.

        This method performs exactly one connection attempt.
        Reconnection policy is handled separately.
        """
        websocket = self._load_websocket_module()

        uri = get_authorized_websocket_uri(
            self.config.access_token,
            timeout_seconds=self.config.timeout_seconds,
        )

        self._ws = websocket.create_connection(
            uri,
            timeout=self.config.timeout_seconds,
        )

    def _resubscribe(self) -> None:
        """Restore subscriptions after a successful reconnect.

        The existing symbol set is intentionally preserved during reconnect.
        """
        if self._subscribed_symbols:
            symbols = sorted(self._subscribed_symbols)

            # Send the subscription without changing the stored symbol set.
            websocket = self._load_websocket_module()

            instrument_keys = [
                self.instrument_mapper.instrument_key(symbol)
                for symbol in symbols
            ]

            request = {
                "guid": str(uuid.uuid4()),
                "method": "sub",
                "data": {
                    "mode": self.config.mode,
                    "instrumentKeys": instrument_keys,
                },
            }

            # Upstox V3 expects subscription requests as binary frames.
            self._ws.send(
                json.dumps(request).encode("utf-8"),
                opcode=websocket.ABNF.OPCODE_BINARY,
            )

    def _reconnect(self) -> bool:
        """Reconnect and restore subscriptions.

        Returns:
            True when reconnection succeeds.
            False when all configured attempts fail.
        """
        # Preserve the current subscription state before replacing the socket.
        subscribed_symbols = set(self._subscribed_symbols)

        for attempt in range(1, self.config.reconnect_max_attempts + 1):
            if self.metrics is not None:
                self.metrics.record_reconnect_attempt()

            try:
                # Close the failed socket without clearing subscriptions.
                if self._ws is not None:
                    try:
                        self._ws.close()
                    except Exception:
                        pass

                self._ws = None

                if self.config.reconnect_delay_seconds > 0:
                    time.sleep(self.config.reconnect_delay_seconds)

                self._open_connection()

                # Restore subscriptions directly from the preserved state.
                self._subscribed_symbols = subscribed_symbols
                self._resubscribe()

                if self.metrics is not None:
                    self.metrics.record_reconnect_success()

                return True

            except Exception:
                self._ws = None

        if self.metrics is not None:
            self.metrics.record_reconnect_failure()

        return False

    def connect(self) -> None:
        """Authorize and open the provider WebSocket connection."""
        self._open_connection()

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
        from .proto_adapter import extract_ltpc

        while True:
            received_timestamp = datetime.now().astimezone()

            try:
                raw_message = self._ws.recv()
            except Exception as exc:
                # Determine whether the exception represents a connection
                # failure that can safely trigger the reconnect policy.
                websocket = self._load_websocket_module()

                websocket_exception = getattr(
                    websocket,
                    "WebSocketException",
                    (),
                )

                is_connection_failure = isinstance(
                    exc,
                    (
                        ConnectionError,
                        OSError,
                        TimeoutError,
                    ),
                )

                if websocket_exception:
                    is_connection_failure = (
                        is_connection_failure
                        or isinstance(exc, websocket_exception)
                    )

                if not is_connection_failure:
                    raise

                # Record the provider connection failure exactly once,
                # after confirming that this is a connection-related error.
                if self.metrics is not None:
                    self.metrics.record_connection_failure()

                if not self._reconnect():
                    raise RuntimeError(
                        "Upstox market feed reconnect attempts exhausted"
                    ) from exc

                # The connection has been restored and subscriptions have
                # been replayed. Continue receiving market events.
                continue
            if raw_message is None:
                return
            if isinstance(raw_message, str):
                # V3 market updates are binary protobuf frames.
                continue

            decoded = decode_feed_message(
                raw_message,
                self._protobuf_module,
            )

            # Keep protobuf-specific field extraction inside the adapter.
            records = extract_ltpc(decoded)

            for record in records:
                instrument_key = record.instrument_key

                symbol = next(
                    (
                        candidate
                        for candidate in self._subscribed_symbols
                        if self.instrument_mapper.instrument_key(candidate)
                        == instrument_key
                    ),
                    instrument_key,
                )

                event_timestamp = epoch_millis_to_datetime(
                    record.timestamp_ms,
                )

                event = MarketEvent(
                    event_id=(
                        f"{instrument_key}:{record.timestamp_ms}:"
                        f"{int(record.quantity)}"
                    ),
                    symbol=symbol,
                    exchange="NSE",
                    event_type=MarketEventType.TRADE,
                    price=record.price,
                    volume=record.quantity,
                    exchange_timestamp=event_timestamp,
                    received_timestamp=received_timestamp,
                    sequence_number=record.sequence_number,
                )

                # Validate and record telemetry only when the components are configured.
                if self.event_validator is not None:
                    validation_result = self.event_validator.validate(event)

                    if self.metrics is not None:
                        self.metrics.record_validation(validation_result)

                    # Invalid events must never enter the downstream trading pipeline.
                    if not validation_result.valid:
                        continue

                yield event

    def disconnect(self) -> None:
        """Close the active provider connection safely."""
        if self._ws is not None:
            self._ws.close()
        self._ws = None
        self._subscribed_symbols.clear()
