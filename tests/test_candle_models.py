"""Tests for the canonical OHLCV Candle model."""

from datetime import datetime, timezone

import pytest

from market.candles.models import Candle


def make_valid_candle() -> Candle:
    """Create a valid five-minute candle for testing."""
    return Candle(
        symbol="ITC",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=datetime(
            2026,
            9,
            1,
            9,
            15,
            tzinfo=timezone.utc,
        ),
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=1000.0,
    )


def test_valid_candle_is_created() -> None:
    """A valid OHLCV candle should be accepted."""
    candle = make_valid_candle()

    assert candle.symbol == "ITC"
    assert candle.exchange == "NSE"
    assert candle.timeframe_minutes == 5
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 98.0
    assert candle.close == 103.0
    assert candle.volume == 1000.0


def test_candle_requires_timezone_aware_timestamp() -> None:
    """Naive timestamps must be rejected."""
    with pytest.raises(ValueError, match="timezone-aware"):
        Candle(
            symbol="ITC",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(2026, 9, 1, 9, 15),
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000.0,
        )


def test_high_cannot_be_below_open() -> None:
    """High must contain the complete candle price range."""
    with pytest.raises(ValueError, match="high"):
        Candle(
            symbol="ITC",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                9,
                1,
                9,
                15,
                tzinfo=timezone.utc,
            ),
            open=110.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=1000.0,
        )


def test_low_cannot_be_above_close() -> None:
    """Low must contain the complete candle price range."""
    with pytest.raises(ValueError, match="low"):
        Candle(
            symbol="ITC",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                9,
                1,
                9,
                15,
                tzinfo=timezone.utc,
            ),
            open=100.0,
            high=105.0,
            low=104.0,
            close=103.0,
            volume=1000.0,
        )


def test_negative_volume_is_rejected() -> None:
    """Volume cannot be negative."""
    with pytest.raises(ValueError, match="volume"):
        Candle(
            symbol="ITC",
            exchange="NSE",
            timeframe_minutes=5,
            timestamp=datetime(
                2026,
                9,
                1,
                9,
                15,
                tzinfo=timezone.utc,
            ),
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=-1.0,
        )
