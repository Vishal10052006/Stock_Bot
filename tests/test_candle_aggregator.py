"""Tests for MarketEvent to OHLCV candle aggregation."""

from datetime import datetime, timezone

import pytest

from market.candles.aggregator import CandleAggregator
from market.data.events import MarketEvent, MarketEventType


def make_event(
    timestamp: datetime,
    price: float,
    volume: float,
    *,
    symbol: str = "ITC",
) -> MarketEvent:
    """Create a canonical trade event for testing."""
    return MarketEvent(
        event_id=f"{symbol}-{timestamp.isoformat()}-{price}",
        symbol=symbol,
        exchange="NSE",
        event_type=MarketEventType.TRADE,
        price=price,
        volume=volume,
        exchange_timestamp=timestamp,
        received_timestamp=timestamp,
    )


def ist_timestamp(
    hour: int,
    minute: int,
    second: int = 0,
) -> datetime:
    """Create an IST timestamp."""
    from zoneinfo import ZoneInfo

    return datetime(
        2026,
        9,
        1,
        hour,
        minute,
        second,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )


def test_first_event_starts_candle() -> None:
    """The first event should create an in-progress candle."""
    aggregator = CandleAggregator()

    result = aggregator.update(
        make_event(
            ist_timestamp(9, 15, 1),
            100.0,
            10.0,
        )
    )

    assert result is None


def test_ohlcv_is_aggregated_correctly() -> None:
    """Events within one bucket should produce correct OHLCV."""
    aggregator = CandleAggregator()

    aggregator.update(
        make_event(
            ist_timestamp(9, 15, 1),
            100.0,
            10.0,
        )
    )

    aggregator.update(
        make_event(
            ist_timestamp(9, 16, 0),
            105.0,
            20.0,
        )
    )

    aggregator.update(
        make_event(
            ist_timestamp(9, 18, 0),
            98.0,
            30.0,
        )
    )

    aggregator.update(
        make_event(
            ist_timestamp(9, 19, 59),
            103.0,
            40.0,
        )
    )

    candle = aggregator.flush()[0]

    assert candle.timestamp == ist_timestamp(9, 15)
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 98.0
    assert candle.close == 103.0
    assert candle.volume == 100.0


def test_next_bucket_emits_previous_candle() -> None:
    """An event in the next bucket should emit the previous candle."""
    aggregator = CandleAggregator()

    aggregator.update(
        make_event(
            ist_timestamp(9, 15),
            100.0,
            10.0,
        )
    )

    completed = aggregator.update(
        make_event(
            ist_timestamp(9, 20),
            110.0,
            20.0,
        )
    )

    assert completed is not None
    assert completed.timestamp == ist_timestamp(9, 15)
    assert completed.open == 100.0
    assert completed.high == 100.0
    assert completed.low == 100.0
    assert completed.close == 100.0
    assert completed.volume == 10.0


def test_multiple_symbols_are_isolated() -> None:
    """Each symbol must maintain an independent candle."""
    aggregator = CandleAggregator()

    aggregator.update(
        make_event(
            ist_timestamp(9, 15),
            100.0,
            10.0,
            symbol="ITC",
        )
    )

    aggregator.update(
        make_event(
            ist_timestamp(9, 15),
            200.0,
            20.0,
            symbol="RELIANCE",
        )
    )

    # Moving ITC into the next bucket completes only ITC's
    # previous candle. RELIANCE remains in its own active bucket.
    completed_itc = aggregator.update(
        make_event(
            ist_timestamp(9, 20),
            110.0,
            5.0,
            symbol="ITC",
        )
    )

    assert completed_itc is not None
    assert completed_itc.symbol == "ITC"
    assert completed_itc.timestamp == ist_timestamp(9, 15)
    assert completed_itc.open == 100.0
    assert completed_itc.high == 100.0
    assert completed_itc.low == 100.0
    assert completed_itc.close == 100.0
    assert completed_itc.volume == 10.0

    # ITC now has a new active candle, while RELIANCE still has
    # its original active candle. They must remain isolated.
    active_candles = aggregator.flush()

    assert len(active_candles) == 2

    itc = next(
        candle
        for candle in active_candles
        if candle.symbol == "ITC"
    )

    reliance = next(
        candle
        for candle in active_candles
        if candle.symbol == "RELIANCE"
    )

    assert itc.timestamp == ist_timestamp(9, 20)
    assert itc.open == 110.0
    assert itc.volume == 5.0

    assert reliance.timestamp == ist_timestamp(9, 15)
    assert reliance.open == 200.0
    assert reliance.volume == 20.0


def test_events_before_session_are_ignored() -> None:
    """Pre-market events must not create candles."""
    aggregator = CandleAggregator()

    result = aggregator.update(
        make_event(
            ist_timestamp(9, 14, 59),
            100.0,
            10.0,
        )
    )

    assert result is None
    assert aggregator.flush() == []


def test_events_at_session_close_are_ignored() -> None:
    """Events at 15:30 belong outside the normal session."""
    aggregator = CandleAggregator()

    result = aggregator.update(
        make_event(
            ist_timestamp(15, 30),
            100.0,
            10.0,
        )
    )

    assert result is None
    assert aggregator.flush() == []


def test_out_of_order_events_are_rejected() -> None:
    """Exchange timestamps must arrive chronologically."""
    aggregator = CandleAggregator()

    aggregator.update(
        make_event(
            ist_timestamp(9, 17),
            100.0,
            10.0,
        )
    )

    with pytest.raises(
        ValueError,
        match="chronological order",
    ):
        aggregator.update(
            make_event(
                ist_timestamp(9, 16),
                101.0,
                10.0,
            )
        )


def test_non_trade_event_is_rejected() -> None:
    """The v1 aggregator only consumes trade events."""
    aggregator = CandleAggregator()

    event = MarketEvent(
        event_id="quote-1",
        symbol="ITC",
        exchange="NSE",
        event_type=MarketEventType.QUOTE,
        price=100.0,
        volume=10.0,
        exchange_timestamp=ist_timestamp(9, 15),
        received_timestamp=ist_timestamp(9, 15),
    )

    with pytest.raises(ValueError, match="trade events only"):
        aggregator.update(event)


def test_flush_specific_symbol() -> None:
    """A single symbol can be flushed without affecting others."""
    aggregator = CandleAggregator()

    aggregator.update(
        make_event(
            ist_timestamp(9, 15),
            100.0,
            10.0,
            symbol="ITC",
        )
    )

    aggregator.update(
        make_event(
            ist_timestamp(9, 15),
            200.0,
            20.0,
            symbol="RELIANCE",
        )
    )

    candles = aggregator.flush("ITC")

    assert len(candles) == 1
    assert candles[0].symbol == "ITC"

    remaining = aggregator.flush()

    assert len(remaining) == 1
    assert remaining[0].symbol == "RELIANCE"
