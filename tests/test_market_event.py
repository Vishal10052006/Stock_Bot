"""Tests for the Phase 3.1 canonical market event contract.

Reference: ROADMAP_STOCK-BOT.pdf, Phase 3 — Real-Time Data Pipeline.
"""

from datetime import datetime, timezone

import pytest

from market.data.events import MarketEvent, MarketEventType


def make_event(**overrides):
    """Build a valid event and apply test-specific overrides."""
    values = {
        "event_id": "evt-1",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "event_type": MarketEventType.TRADE,
        "price": 1425.30,
        "volume": 100.0,
        "exchange_timestamp": datetime(2026, 8, 30, 10, 25, tzinfo=timezone.utc),
        "received_timestamp": datetime(2026, 8, 30, 10, 25, 0, 50_000, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return MarketEvent(**values)


def test_valid_event_is_immutable():
    """Canonical events must not change after entering the pipeline."""
    event = make_event()

    assert event.symbol == "RELIANCE"
    with pytest.raises((AttributeError, TypeError)):
        event.symbol = "TCS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", ""),
        ("symbol", ""),
        ("exchange", ""),
        ("price", 0),
        ("price", -1),
        ("volume", -1),
    ],
)
def test_invalid_values_are_rejected(field, value):
    """Invalid upstream data must fail at the contract boundary."""
    with pytest.raises(ValueError):
        make_event(**{field: value})


def test_timestamps_must_be_timezone_aware():
    """Naive timestamps would make latency calculations unreliable."""
    with pytest.raises(ValueError, match="timezone-aware"):
        make_event(exchange_timestamp=datetime(2026, 8, 30, 10, 25))


def test_sequence_number_must_be_non_negative():
    """Ordering metadata cannot contain negative sequence numbers."""
    with pytest.raises(ValueError, match="non-negative"):
        make_event(sequence_number=-1)
