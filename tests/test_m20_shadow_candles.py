"""Tests for the M20 causal shadow candle buffer."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from market.candles.models import Candle
from runtime.shadow_candles import ShadowCandleBuffer


def _candle(minute: int, symbol: str = "ITC") -> Candle:
    return Candle(
        symbol=symbol,
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=datetime(2026, 9, 28, 9, minute, tzinfo=timezone.utc),
        open=100.0 + minute,
        high=101.0 + minute,
        low=99.0 + minute,
        close=100.5 + minute,
        volume=1000.0,
    )


def test_buffer_keeps_bounded_causal_history() -> None:
    buffer = ShadowCandleBuffer(max_candles_per_symbol=2)

    buffer.append(_candle(15))
    buffer.append(_candle(20))
    buffer.append(_candle(25))

    assert buffer.count("itc") == 2
    frame = buffer.frame("ITC")
    assert frame["timestamp"].tolist() == [
        _candle(20).timestamp,
        _candle(25).timestamp,
    ]


def test_buffer_rejects_duplicate_and_out_of_order_candles() -> None:
    buffer = ShadowCandleBuffer()
    buffer.append(_candle(15))

    with pytest.raises(ValueError, match="duplicate"):
        buffer.append(_candle(15))

    with pytest.raises(ValueError, match="chronological"):
        buffer.append(_candle(10))


def test_buffer_keeps_symbols_independent() -> None:
    buffer = ShadowCandleBuffer()
    buffer.append(_candle(15, "ITC"))
    buffer.append(_candle(15, "TCS"))

    assert buffer.symbols() == ("ITC", "TCS")
    assert buffer.count("ITC") == 1
    assert buffer.count("TCS") == 1


def test_buffer_requires_positive_capacity() -> None:
    with pytest.raises(ValueError, match="positive"):
        ShadowCandleBuffer(max_candles_per_symbol=0)
