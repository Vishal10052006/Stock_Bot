"""Decode Upstox Market Data Feed V3 protobuf payloads.

Provider-specific protobuf details remain isolated from the rest of Stock Bot.

Reference:
    Upstox Market Data Feed V3 protobuf schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any


class UpstoxDecodeError(ValueError):
    """Raised when an upstream market-data message cannot be decoded."""


def _resolve_feed_response(protobuf_module: Any) -> Any:
    """Return the generated ``FeedResponse`` message class."""
    message_class = getattr(protobuf_module, "FeedResponse", None)
    if message_class is not None:
        return message_class

    nested = getattr(protobuf_module, "MarketDataFeedV3_pb2", None)
    if nested is not None and hasattr(nested, "FeedResponse"):
        return nested.FeedResponse

    raise ValueError("protobuf_module must expose FeedResponse")


def decode_feed_message(payload: bytes, protobuf_module: Any | None = None) -> Any:
    """Decode raw V3 protobuf bytes into a generated ``FeedResponse`` object.

    The generated protobuf dependency can be injected for tests. In production
    it is loaded from the adapter's generated package.
    """
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")

    if protobuf_module is None:
        try:
            protobuf_module = import_module(
                "market.data.ingestion.providers.upstox.generated.MarketDataFeedV3_pb2"
            )
        except ModuleNotFoundError as exc:
            raise UpstoxDecodeError(
                "Generated Upstox protobuf module is not installed"
            ) from exc

    try:
        feed_response = _resolve_feed_response(protobuf_module)
    except ValueError:
        # Preserve dependency-contract errors so callers can distinguish a
        # missing generated message class from malformed wire data.
        raise

    try:
        return feed_response.FromString(bytes(payload))
    except Exception as exc:
        raise UpstoxDecodeError("Unable to decode Upstox protobuf payload") from exc


def epoch_millis_to_datetime(value: int | str) -> datetime:
    """Convert epoch milliseconds into a timezone-aware UTC datetime."""
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as exc:
        raise UpstoxDecodeError("timestamp must be an integer epoch value") from exc

    return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc)
