"""Decode Upstox Market Data Feed V3 protobuf payloads."""

from __future__ import annotations

from datetime import datetime, timezone


class UpstoxDecodeError(ValueError):
    """Raised when an upstream market-data message cannot be decoded."""


def decode_feed_message(payload: bytes, protobuf_module):
    """Decode raw protobuf bytes with the supplied generated module.

    The generated protobuf module is injected so the core adapter remains
    testable without requiring generated provider code in every unit test.

    Reference:
        Upstox Market Data Feed V3 uses protobuf-encoded WebSocket messages.
    """
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")
    if protobuf_module is None or not hasattr(protobuf_module, "FeedResponse"):
        raise ValueError("protobuf_module must expose FeedResponse")

    try:
        return protobuf_module.FeedResponse.FromString(bytes(payload))
    except Exception as exc:
        raise UpstoxDecodeError("Unable to decode Upstox protobuf payload") from exc


def epoch_millis_to_datetime(value: int | str) -> datetime:
    """Convert provider epoch milliseconds into a timezone-aware UTC datetime."""
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as exc:
        raise UpstoxDecodeError("timestamp must be an integer epoch value") from exc

    return datetime.fromtimestamp(milliseconds / 1000.0, tz=timezone.utc)
