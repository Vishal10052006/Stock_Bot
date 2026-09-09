"""Tests for the Upstox V3 protobuf decoding boundary.

Reference: Phase 3.2 — Live Market Feed.
"""

from datetime import datetime, timezone

import pytest

from market.data.ingestion.providers.upstox.decoder import (
    UpstoxDecodeError,
    decode_feed_message,
    epoch_millis_to_datetime,
)


class FakeFeedResponse:
    """Minimal protobuf-like stand-in for deterministic unit tests."""

    last_payload = None

    @classmethod
    def FromString(cls, payload: bytes):
        """Record the payload exactly as a protobuf generated class would receive it."""
        cls.last_payload = payload
        if payload == b"bad":
            raise ValueError("invalid protobuf")
        return {"decoded": payload}


class FakeProtoModule:
    """Container exposing the generated-message contract."""

    FeedResponse = FakeFeedResponse


def test_decode_feed_message_accepts_bytes_like_payload():
    """Decoder must pass raw wire bytes to the generated message class."""
    decoded = decode_feed_message(bytearray(b"market"), FakeProtoModule)

    assert decoded == {"decoded": b"market"}
    assert FakeFeedResponse.last_payload == b"market"


def test_decode_feed_message_rejects_non_bytes_payload():
    """Wire payloads must be bytes-like before protobuf parsing."""
    with pytest.raises(TypeError, match="bytes-like"):
        decode_feed_message("market", FakeProtoModule)


def test_decode_feed_message_wraps_protobuf_errors():
    """Provider decoder errors should use our stable exception type."""
    with pytest.raises(UpstoxDecodeError, match="Unable to decode"):
        decode_feed_message(b"bad", FakeProtoModule)


def test_decode_feed_message_requires_feed_response():
    """Injected modules must expose the expected generated message class."""
    with pytest.raises(ValueError, match="FeedResponse"):
        decode_feed_message(b"market", object())


def test_epoch_millis_conversion_is_timezone_aware():
    """Provider epoch milliseconds must become timezone-aware UTC datetimes."""
    result = epoch_millis_to_datetime(0)

    assert result == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert result.tzinfo == timezone.utc


def test_epoch_millis_rejects_invalid_values():
    """Malformed provider timestamps must fail predictably."""
    with pytest.raises(UpstoxDecodeError, match="timestamp"):
        epoch_millis_to_datetime("not-a-number")
