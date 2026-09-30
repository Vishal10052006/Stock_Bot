"""Regression tests for live model runtime candle normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from market.candles.models import Candle
from ml.prediction.live_runtime import LiveModelRuntime


def _candle(timestamp: datetime) -> Candle:
    return Candle(
        symbol="RELIANCE",
        exchange="NSE",
        timeframe_minutes=5,
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )


def test_frame_normalizes_mixed_timezone_candles_to_utc() -> None:
    bars = [
        _candle(
            datetime(
                2026,
                9,
                30,
                9,
                15,
                tzinfo=ZoneInfo("Asia/Kolkata"),
            )
        ),
        _candle(
            datetime(
                2026,
                9,
                30,
                3,
                50,
                tzinfo=timezone.utc,
            )
        ),
    ]

    frame = LiveModelRuntime._frame(bars)

    assert isinstance(frame["timestamp"].dtype, pd.DatetimeTZDtype)
    assert str(frame["timestamp"].dt.tz) == "UTC"
    assert frame["timestamp"].tolist() == [
        pd.Timestamp("2026-09-30 03:45:00+00:00"),
        pd.Timestamp("2026-09-30 03:50:00+00:00"),
    ]
