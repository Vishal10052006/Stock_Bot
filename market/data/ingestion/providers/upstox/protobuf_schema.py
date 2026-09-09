"""Minimal Upstox V3 protobuf schema boundary.

This module defines the field numbers required to decode the LTPC subset used
by the first Phase 3.2 milestone. It intentionally keeps wire-format parsing
small and isolated from the provider adapter.

Reference:
    Upstox Market Data Feed V3 protobuf WebSocket protocol.
"""

from __future__ import annotations

from dataclasses import dataclass


class ProtobufWireError(ValueError):
    """Raised when a protobuf wire payload is malformed."""


def _read_varint(data: bytes, index: int) -> tuple[int, int]:
    """Read a protobuf varint and return ``(value, next_index)``."""
    value = 0
    shift = 0

    while index < len(data):
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7
        if shift >= 64:
            raise ProtobufWireError("varint is too long")

    raise ProtobufWireError("truncated varint")


def _read_length_delimited(data: bytes, index: int) -> tuple[bytes, int]:
    """Read a protobuf length-delimited field."""
    length, index = _read_varint(data, index)
    end = index + length
    if end > len(data):
        raise ProtobufWireError("truncated length-delimited field")
    return data[index:end], end


def iter_fields(data: bytes):
    """Yield protobuf fields as ``(field_number, wire_type, value)``."""
    index = 0
    while index < len(data):
        key, index = _read_varint(data, index)
        field_number = key >> 3
        wire_type = key & 0x07
        if field_number <= 0:
            raise ProtobufWireError("invalid protobuf field number")

        if wire_type == 0:
            value, index = _read_varint(data, index)
        elif wire_type == 2:
            value, index = _read_length_delimited(data, index)
        elif wire_type == 1:
            end = index + 8
            if end > len(data):
                raise ProtobufWireError("truncated fixed64 field")
            value, index = data[index:end], end
        elif wire_type == 5:
            end = index + 4
            if end > len(data):
                raise ProtobufWireError("truncated fixed32 field")
            value, index = data[index:end], end
        else:
            raise ProtobufWireError(f"unsupported protobuf wire type: {wire_type}")

        yield field_number, wire_type, value


@dataclass(frozen=True, slots=True)
class RawFeedMessage:
    """Provider-neutral intermediate representation of a decoded feed."""

    payload: bytes
