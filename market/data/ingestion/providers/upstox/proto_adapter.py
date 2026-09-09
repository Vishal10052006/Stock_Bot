"""Stable extraction boundary for generated Upstox protobuf messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DecodedLTP:
    """Provider-normalized LTPC values needed to construct a MarketEvent."""

    instrument_key: str
    price: float
    quantity: float
    timestamp_ms: int
    sequence_number: int | None = None


def extract_ltpc(feed_response: Any) -> list[DecodedLTP]:
    """Extract LTPC records from a generated ``FeedResponse`` message.

    The adapter tolerates protobuf map containers and normal Python mappings,
    which keeps unit tests independent of the protobuf runtime implementation.
    """
    feeds = getattr(feed_response, "feeds", None)
    if not feeds:
        return []

    records: list[DecodedLTP] = []
    for instrument_key, feed in feeds.items():
        ltpc = getattr(feed, "ltpc", None)
        if ltpc is None:
            continue

        try:
            price = float(getattr(ltpc, "ltp"))
            quantity = float(getattr(ltpc, "ltq", 0))
            timestamp_ms = int(getattr(ltpc, "ltt"))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(
                f"invalid LTPC values for instrument {instrument_key}"
            ) from exc

        sequence = getattr(ltpc, "sequence_number", None)
        records.append(
            DecodedLTP(
                instrument_key=str(instrument_key),
                price=price,
                quantity=quantity,
                timestamp_ms=timestamp_ms,
                sequence_number=(int(sequence) if sequence is not None else None),
            )
        )

    return records
