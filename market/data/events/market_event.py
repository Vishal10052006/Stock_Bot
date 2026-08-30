"""Canonical market event contract for the Phase 3 real-time pipeline."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite


class MarketEventType(str, Enum):
    """Supported real-time market event categories."""

    TRADE = "trade"
    QUOTE = "quote"
    BAR = "bar"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """Immutable, provider-neutral market event consumed downstream."""

    event_id: str
    symbol: str
    exchange: str
    event_type: MarketEventType
    price: float
    volume: float
    exchange_timestamp: datetime
    received_timestamp: datetime
    sequence_number: int | None = None

    def __post_init__(self) -> None:
        """Fail fast when an upstream adapter produces an invalid event."""
        if not self.event_id.strip():
            raise ValueError("event_id must not be empty")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.exchange.strip():
            raise ValueError("exchange must not be empty")
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("price must be finite and greater than zero")
        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError("volume must be finite and non-negative")
        if self.exchange_timestamp.tzinfo is None:
            raise ValueError("exchange_timestamp must be timezone-aware")
        if self.received_timestamp.tzinfo is None:
            raise ValueError("received_timestamp must be timezone-aware")
        if self.sequence_number is not None and self.sequence_number < 0:
            raise ValueError("sequence_number must be non-negative")
