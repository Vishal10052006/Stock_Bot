"""Tests for canonical real-time market-event validation."""

from datetime import datetime, timezone

import pytest

from market.data.events import MarketEvent, MarketEventType
from market.data.validation import MarketEventValidator


UTC = timezone.utc


def make_event(**overrides):
    """Build a deterministic valid market event."""
    values = {
        "event_id": "evt-1",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "event_type": MarketEventType.TRADE,
        "price": 1425.30,
        "volume": 100.0,
        "exchange_timestamp": datetime(
            2026,
            8,
            31,
            10,
            25,
            tzinfo=UTC,
        ),
        "received_timestamp": datetime(
            2026,
            8,
            31,
            10,
            25,
            0,
            100_000,
            tzinfo=UTC,
        ),
    }

    values.update(overrides)

    return MarketEvent(**values)


def test_valid_event_passes_validation():
    """A fresh event with reasonable latency should be accepted."""
    validator = MarketEventValidator()

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        1,
        tzinfo=UTC,
    )

    event = make_event()

    result = validator.validate(event, now=now)

    assert result.valid is True
    assert result.stale is False
    assert result.duplicate is False
    assert result.reason is None
    assert result.latency_ms == pytest.approx(100.0)


def test_stale_event_is_rejected():
    """Events older than the freshness threshold must be rejected."""
    validator = MarketEventValidator(
        max_event_age_seconds=5.0,
    )

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        10,
        tzinfo=UTC,
    )

    event = make_event()

    result = validator.validate(event, now=now)

    assert result.valid is False
    assert result.stale is True
    assert result.reason == "event is stale"


def test_duplicate_event_is_rejected():
    """The same event ID must not enter the pipeline twice."""
    validator = MarketEventValidator()

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        1,
        tzinfo=UTC,
    )

    event = make_event()

    first = validator.validate(event, now=now)
    second = validator.validate(event, now=now)

    assert first.valid is True
    assert second.valid is False
    assert second.duplicate is True
    assert second.reason == "duplicate event"


def test_future_timestamp_is_rejected():
    """Exchange timestamps too far ahead indicate clock/data problems."""
    validator = MarketEventValidator(
        max_future_skew_seconds=2.0,
    )

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        tzinfo=UTC,
    )

    event = make_event(
        exchange_timestamp=datetime(
            2026,
            8,
            31,
            10,
            25,
            5,
            tzinfo=UTC,
        )
    )

    result = validator.validate(event, now=now)

    assert result.valid is False
    assert result.reason == "exchange timestamp is too far in the future"


def test_small_clock_skew_is_allowed():
    """Small negative latency should be tolerated as clock skew."""
    validator = MarketEventValidator(
        max_future_skew_seconds=2.0,
    )

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        tzinfo=UTC,
    )

    event = make_event(
        exchange_timestamp=datetime(
            2026,
            8,
            31,
            10,
            25,
            0,
            500_000,
            tzinfo=UTC,
        )
    )

    result = validator.validate(event, now=now)

    assert result.valid is True
    assert result.latency_ms == pytest.approx(-400.0)


def test_invalid_constructor_configuration_is_rejected():
    """Validator thresholds must have safe values."""
    with pytest.raises(ValueError):
        MarketEventValidator(max_event_age_seconds=0)

    with pytest.raises(ValueError):
        MarketEventValidator(max_future_skew_seconds=-1)


def test_reset_allows_event_id_again():
    """Reset should clear duplicate-detection state."""
    validator = MarketEventValidator()

    now = datetime(
        2026,
        8,
        31,
        10,
        25,
        1,
        tzinfo=UTC,
    )

    event = make_event()

    assert validator.validate(event, now=now).valid is True
    assert validator.validate(event, now=now).duplicate is True

    validator.reset()

    assert validator.validate(event, now=now).valid is True
